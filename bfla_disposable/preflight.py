"""Preflight attestation for a one-run disposable BFLA environment."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from typing import Any

from vampi_authz_lab.common import read_json, write_redacted_json

from .manifest import (
    ALLOWED_BASE_URL,
    BflaManifestError,
    WORKFLOW,
    load_manifest,
    manifest_path,
    receipt_path,
    teardown_receipt_path,
    validate_project_name,
    validate_run_directory,
    validate_run_id,
)
from .runner import _assert_private_directory


def preflight_receipt_path(run_id: str, results_root: str | Path = "results/bfla-disposable") -> Path:
    """Return the non-secret preflight receipt path for one disposable run."""
    return Path(results_root) / validate_run_id(run_id) / "preflight-receipt.json"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def shared_week1_snapshot() -> dict[str, str]:
    """Read only the shared-lab identity/state needed for non-interference proof."""
    result = _run(["docker", "inspect", "vampi-week1", "--format", "{{.Id}} {{.State.Status}}"])
    if result.returncode != 0:
        raise BflaManifestError("Shared vampi-week1 container could not be attested.")
    parts = result.stdout.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[1] != "running":
        raise BflaManifestError("Shared vampi-week1 must already be running; preflight will not start or alter it.")
    return {"id": parts[0], "state": parts[1]}


def _assert_port_available() -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 5003))
    except OSError as error:
        raise BflaManifestError("Disposable BFLA port 127.0.0.1:5003 is already occupied.") from error
    finally:
        probe.close()


def _assert_project_absent(project: str) -> None:
    containers = _run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.ID}}"])
    volumes = _run(["docker", "volume", "ls", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Name}}"])
    if containers.returncode != 0 or volumes.returncode != 0:
        raise BflaManifestError("Unable to inspect existing disposable Docker objects.")
    if containers.stdout.strip() or volumes.stdout.strip():
        raise BflaManifestError("Disposable Compose project already has container or volume objects.")


def _image_id() -> str:
    result = _run(["docker", "image", "inspect", "vampi-week1:local", "--format", "{{.Id}}"])
    if result.returncode != 0 or not result.stdout.strip():
        raise BflaManifestError("Disposable VAmPI image vampi-week1:local could not be attested.")
    return result.stdout.strip()


def _assert_new_run_artifacts(run_id: str, results_root: str | Path) -> None:
    for path in (
        preflight_receipt_path(run_id, results_root),
        receipt_path(run_id, results_root),
        teardown_receipt_path(run_id, results_root),
    ):
        if path.exists() or path.is_symlink():
            raise BflaManifestError("Disposable run ID already has a durable execution-stage artifact.")


def load_preflight_receipt(run_id: str, project: str, results_root: str | Path = "results/bfla-disposable") -> dict[str, Any]:
    """Load an immutable preflight receipt and bind it to this exact run/project."""
    run_id = validate_run_id(run_id)
    validate_project_name(project, run_id)
    receipt = read_json(preflight_receipt_path(run_id, results_root))
    if not isinstance(receipt, dict):
        raise BflaManifestError("Disposable preflight receipt must be an object.")
    expected_project = project
    expected_fields = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "run_id": run_id,
        "target": ALLOWED_BASE_URL,
        "compose_project": expected_project,
        "port_5003_available_before_compose": True,
        "existing_project_objects": {"containers": [], "volumes": []},
        "credential_or_response_bodies_exported": False,
        "status": "PREFLIGHT_COMPLETE",
    }
    if any(receipt.get(key) != value for key, value in expected_fields.items()):
        raise BflaManifestError("Disposable preflight receipt differs from the approved run scope.")
    shared = receipt.get("shared_week1_before")
    if not isinstance(shared, dict) or not isinstance(shared.get("id"), str) or shared.get("state") != "running":
        raise BflaManifestError("Disposable preflight receipt lacks a valid shared-lab snapshot.")
    image_id = receipt.get("disposable_image_id")
    if not isinstance(image_id, str) or not image_id:
        raise BflaManifestError("Disposable preflight receipt lacks an attested image identity.")
    return receipt


def preflight(
    run_id: str,
    project: str,
    run_dir: str | Path,
    results_root: str | Path = "results/bfla-disposable",
) -> dict[str, Any]:
    """Attest the isolated destination before Compose creates disposable objects."""
    run_id = validate_run_id(run_id)
    validate_project_name(project, run_id)
    directory = validate_run_directory(run_dir, run_id)
    public_manifest = manifest_path(run_id, results_root)
    if not public_manifest.is_file() or public_manifest.is_symlink():
        raise BflaManifestError("Create the credential-free destructive manifest before preflight.")
    manifest = load_manifest(public_manifest)
    if manifest["target"]["compose_project"] != project:
        raise BflaManifestError("Public manifest project does not match the requested disposable project.")
    _assert_new_run_artifacts(run_id, results_root)
    _assert_private_directory(directory)
    if any(directory.iterdir()):
        raise BflaManifestError("Disposable run directory must be empty before preflight.")
    _assert_port_available()
    shared = shared_week1_snapshot()
    _assert_project_absent(project)
    receipt = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "run_id": run_id,
        "target": ALLOWED_BASE_URL,
        "compose_project": project,
        "shared_week1_before": shared,
        "disposable_image_id": _image_id(),
        "port_5003_available_before_compose": True,
        "existing_project_objects": {"containers": [], "volumes": []},
        "credential_or_response_bodies_exported": False,
        "status": "PREFLIGHT_COMPLETE",
    }
    write_redacted_json(preflight_receipt_path(run_id, results_root), receipt)
    return receipt
