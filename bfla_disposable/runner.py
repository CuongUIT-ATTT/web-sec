"""Narrow HTTP workflow for an isolated, disposable VAmPI BFLA test."""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from vampi_authz_lab.common import write_redacted_json

from .manifest import (
    ALLOWED_BASE_URL,
    BflaManifestError,
    load_manifest,
    manifest_path,
    receipt_path,
    validate_base_url,
    validate_project_name,
    validate_run_directory,
    validate_run_id,
)

SECRET_FILE_NAME = "roles.secret.json"
SECRET_KEY_PATTERN = re.compile(r"(?:password|token|authorization|secret)", re.IGNORECASE)


class BflaExecutionError(RuntimeError):
    """Raised when the disposable environment cannot produce a valid control."""


def secret_path(run_dir: str | Path) -> Path:
    """Return the only allowable local secret file location for a run directory."""
    return Path(run_dir) / SECRET_FILE_NAME


def _assert_private_directory(run_dir: Path) -> None:
    if run_dir.is_symlink():
        raise BflaManifestError("Disposable run directory must not be a symlink.")
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not run_dir.is_dir():
        raise BflaManifestError("Disposable run path must be a directory.")
    os.chmod(run_dir, 0o700)
    if stat.S_IMODE(run_dir.stat().st_mode) != 0o700:
        raise BflaManifestError("Disposable run directory must have mode 0700.")


def _random_password() -> str:
    return secrets.token_urlsafe(24)


def _assert_request_scope(path: str, method: str, payload: dict[str, str] | None) -> None:
    allowed_operations = {
        ("GET", "/createdb"),
        ("POST", "/users/v1/register"),
        ("POST", "/users/v1/login"),
    }
    if (method, path) in allowed_operations:
        return
    if method == "GET" and path.startswith("/users/v1/") and path.count("/") == 3:
        return
    if method == "DELETE" and path.startswith("/users/v1/") and path.count("/") == 3 and payload is None:
        return
    raise BflaManifestError("Disposable request falls outside the fixed BFLA workflow scope.")


def _assert_manifest_target(path: str, target: dict[str, Any]) -> None:
    """Bind profile/delete access to a concrete immutable manifest entry."""
    if path != target.get("path"):
        raise BflaManifestError("Disposable request does not match its declared manifest target.")


def _request(path: str, method: str, *, token: str | None = None, payload: dict[str, str] | None = None) -> tuple[int, Any]:
    validate_base_url(ALLOWED_BASE_URL)
    if not path.startswith("/") or "?" in path or "#" in path:
        raise BflaManifestError("Disposable requests require exact path-only targets.")
    _assert_request_scope(path, method, payload)
    headers: dict[str, str] = {"Accept": "application/json"}
    body: bytes | None = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{ALLOWED_BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            raw_body = response.read(16_384)
            status = response.status
    except HTTPError as error:
        raw_body = error.read(16_384)
        status = error.code
    try:
        return status, json.loads(raw_body.decode("utf-8")) if raw_body else None
    except json.JSONDecodeError:
        return status, None


def _create_user(username: str, password: str) -> None:
    status, _ = _request(
        "/users/v1/register",
        "POST",
        payload={"username": username, "password": password, "email": f"{username}@example.test"},
    )
    if status not in {200, 201}:
        raise BflaExecutionError(f"Disposable fixture registration failed for generated user ({status}).")


def _login(username: str, password: str) -> str:
    status, body = _request("/users/v1/login", "POST", payload={"username": username, "password": password})
    token = body.get("auth_token") if isinstance(body, dict) else None
    if status != 200 or not isinstance(token, str) or not token:
        raise BflaExecutionError(f"Disposable fixture login failed for generated role ({status}).")
    return token


def _write_secret(run_dir: Path, value: dict[str, Any]) -> Path:
    _assert_private_directory(run_dir)
    destination = secret_path(run_dir)
    if destination.exists() or destination.is_symlink():
        raise BflaManifestError("Disposable secret path must not already exist or be a symlink.")
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    if stat.S_IMODE(destination.stat().st_mode) != 0o600:
        raise BflaManifestError("Disposable secret file must have mode 0600.")
    return destination


def _load_secret(run_dir: Path) -> dict[str, Any]:
    source = secret_path(run_dir)
    if source.is_symlink() or not source.is_file() or stat.S_IMODE(source.stat().st_mode) != 0o600:
        raise BflaManifestError("Disposable secret file is absent, unsafe, or has the wrong mode.")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BflaManifestError("Disposable secret data is invalid.")
    return data


def _docker_project_containers(project: str) -> list[str]:
    result = subprocess.run(
        ["docker", "ps", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.ID}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BflaExecutionError("Unable to verify the disposable Compose project.")
    return [line for line in result.stdout.splitlines() if line]


def _docker_project_volumes(project: str) -> list[str]:
    result = subprocess.run(
        ["docker", "volume", "ls", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Name}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BflaExecutionError("Unable to verify the disposable Compose volume.")
    return [line for line in result.stdout.splitlines() if line]


def _assert_disposable_runtime(project: str, expected_image_id: str | None = None) -> None:
    containers = _docker_project_containers(project)
    if len(containers) != 1 or len(_docker_project_volumes(project)) != 1:
        raise BflaExecutionError("Disposable project identity or dedicated volume could not be attested.")
    result = subprocess.run(
        ["docker", "inspect", containers[0], "--format", "{{index .Config.Labels \"project.vampi_authz_lab.workflow\"}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "disposable-bfla-v1":
        raise BflaExecutionError("Disposable container lacks the required isolated-workflow identity label.")
    binding = subprocess.run(
        [
            "docker",
            "inspect",
            containers[0],
            "--format",
            "{{.State.Running}} {{(index (index .HostConfig.PortBindings \"5000/tcp\") 0).HostIp}}:{{(index (index .HostConfig.PortBindings \"5000/tcp\") 0).HostPort}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if binding.returncode != 0 or binding.stdout.strip() != "true 127.0.0.1:5003":
        raise BflaExecutionError("Disposable container is not running with the required loopback-only port binding.")
    if expected_image_id is not None:
        image = subprocess.run(
            ["docker", "inspect", containers[0], "--format", "{{.Image}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if image.returncode != 0 or image.stdout.strip() != expected_image_id:
            raise BflaExecutionError("Disposable container image differs from the preflight-attested image.")


def _load_attested_preflight(run_id: str, project: str, results_root: str | Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Require the immutable preflight record and a matching shared-lab snapshot."""
    from .preflight import load_preflight_receipt, shared_week1_snapshot

    receipt = load_preflight_receipt(run_id, project, results_root)
    shared = shared_week1_snapshot()
    if shared != receipt["shared_week1_before"]:
        raise BflaExecutionError("Shared vampi-week1 state differs from the preflight snapshot; disposable work stopped.")
    return receipt, shared


def prepare(run_id: str, project: str, run_dir: str | Path, results_root: str | Path = "results/bfla-disposable") -> Path:
    """Initialize only the separate disposable DB and create its scoped fixtures."""
    run_id = validate_run_id(run_id)
    validate_project_name(project, run_id)
    run_directory = validate_run_directory(run_dir, run_id)
    _assert_private_directory(run_directory)
    public_manifest = manifest_path(run_id, results_root)
    manifest = load_manifest(public_manifest)
    if manifest["target"]["compose_project"] != project:
        raise BflaManifestError("Public manifest project does not match the requested disposable project.")
    preflight_receipt, _ = _load_attested_preflight(run_id, project, results_root)
    _assert_disposable_runtime(project, preflight_receipt["disposable_image_id"])
    if secret_path(run_directory).exists() or secret_path(run_directory).is_symlink():
        raise BflaManifestError("Disposable fixtures were already prepared for this immutable run ID.")
    reset_status, _ = _request("/createdb", "GET")
    if reset_status != 200:
        raise BflaExecutionError(f"Disposable reset failed ({reset_status}).")
    actor_username = f"bfla-{run_id}-actor"
    actor_password = _random_password()
    victim_username = manifest["destructive_targets"][0]["username"]
    victim_password = _random_password()
    control_username = manifest["destructive_targets"][1]["username"]
    control_password = _random_password()
    _create_user(actor_username, actor_password)
    _create_user(victim_username, victim_password)
    _create_user(control_username, control_password)
    actor_token = _login(actor_username, actor_password)
    admin_token = _login("admin", "pass1")
    _write_secret(
        run_directory,
        {
            "run_id": run_id,
            "actor": {"username": actor_username, "password": actor_password, "token": actor_token},
            "admin": {"username": "admin", "password": "pass1", "token": admin_token},
        },
    )
    return public_manifest


def _profile_exists(target: dict[str, Any]) -> tuple[int, bool]:
    path = target.get("path")
    if not isinstance(path, str):
        raise BflaManifestError("Disposable profile check requires a declared manifest target.")
    _assert_manifest_target(path, target)
    status, _ = _request(path, "GET")
    return status, status == 200


def _receipt_record(run_id: str, project: str, protected_status: int, protected_exists: bool, control_status: int | None, control_exists: bool | None, outcome: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workflow": "vampi-disposable-bfla-v1",
        "run_id": run_id,
        "target": ALLOWED_BASE_URL,
        "compose_project": project,
        "operations": {
            "unprivileged_delete": {"status": protected_status, "target_survived": protected_exists},
            "admin_delete_control": {"status": control_status, "target_absent": None if control_exists is None else not control_exists},
        },
        "outcome": outcome,
        "credential_or_response_bodies_exported": False,
    }


def execute(run_id: str, project: str, run_dir: str | Path, results_root: str | Path = "results/bfla-disposable") -> dict[str, Any]:
    """Run precisely the declared non-admin test and the separate admin control."""
    run_id = validate_run_id(run_id)
    validate_project_name(project, run_id)
    manifest = load_manifest(manifest_path(run_id, results_root))
    preflight_receipt, _ = _load_attested_preflight(run_id, project, results_root)
    _assert_disposable_runtime(project, preflight_receipt["disposable_image_id"])
    if receipt_path(run_id, results_root).exists() or receipt_path(run_id, results_root).is_symlink():
        raise BflaManifestError("Disposable execution receipt already exists for this immutable run ID.")
    secret = _load_secret(validate_run_directory(run_dir, run_id))
    if secret.get("run_id") != run_id:
        raise BflaManifestError("Disposable secret run ID does not match the manifest.")
    protected = manifest["destructive_targets"][0]
    control = manifest["destructive_targets"][1]
    _assert_manifest_target(protected["path"], protected)
    _assert_manifest_target(control["path"], control)
    protected_status, _ = _request(protected["path"], "DELETE", token=secret["actor"]["token"])
    _, protected_exists = _profile_exists(protected)
    if protected_status == 200 or not protected_exists:
        result = _receipt_record(run_id, project, protected_status, protected_exists, None, None, "BFLA_CONFIRMED_DESTRUCTIVE")
        write_redacted_json(receipt_path(run_id, results_root), result)
        return result
    if protected_status != protected["expected_status"]:
        result = _receipt_record(run_id, project, protected_status, protected_exists, None, None, "INCONCLUSIVE")
        write_redacted_json(receipt_path(run_id, results_root), result)
        return result
    control_status, _ = _request(control["path"], "DELETE", token=secret["admin"]["token"])
    _, control_exists = _profile_exists(control)
    outcome = "DENIED_CONTROL" if control_status == 200 and not control_exists else "INCONCLUSIVE"
    result = _receipt_record(run_id, project, protected_status, protected_exists, control_status, control_exists, outcome)
    write_redacted_json(receipt_path(run_id, results_root), result)
    return result


def artifact_has_secret_keys(value: Any) -> bool:
    """Test helper for durable artifact key hygiene."""
    if isinstance(value, dict):
        return any(SECRET_KEY_PATTERN.search(str(key)) or artifact_has_secret_keys(item) for key, item in value.items())
    if isinstance(value, list):
        return any(artifact_has_secret_keys(item) for item in value)
    return False
