"""Validation and construction for the opt-in disposable BFLA test manifest."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from vampi_authz_lab.common import read_json, write_redacted_json

ALLOWED_BASE_URL = "http://127.0.0.1:5003"
WORKFLOW = "vampi-disposable-bfla-v1"
PROJECT_PREFIX = "vampi-bfla-"
RUN_ID_PATTERN = re.compile(r"[a-z0-9]{8,32}")


class BflaManifestError(ValueError):
    """Raised when a disposable BFLA manifest falls outside its one-run scope."""


def validate_run_id(run_id: str) -> str:
    """Accept a compact, lowercase identifier safe for Docker project scoping."""
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        raise BflaManifestError("Run ID must contain 8-32 lowercase letters or digits.")
    return run_id


def expected_project_name(run_id: str) -> str:
    """Return the only Compose project name permitted for this run."""
    return f"{PROJECT_PREFIX}{validate_run_id(run_id)}"


def validate_run_directory(run_dir: str | Path, run_id: str) -> Path:
    """Require a non-symlink per-run directory directly beneath .bfla-runs."""
    run_id = validate_run_id(run_id)
    directory = Path(run_dir)
    if (
        directory.name != run_id
        or directory.is_symlink()
        or directory.parent.is_symlink()
        or directory.resolve().parent.name != ".bfla-runs"
    ):
        raise BflaManifestError("Disposable run directory must be a non-symlink direct child of .bfla-runs named by the run ID.")
    return directory


def validate_project_name(project: str, run_id: str) -> str:
    """Require the exact Compose project derived from the validated run ID."""
    if project != expected_project_name(run_id):
        raise BflaManifestError("Compose project does not match the disposable run ID.")
    return project


def validate_base_url(base_url: str) -> str:
    """Allow only the distinct loopback origin reserved for disposable BFLA testing."""
    parsed = urlsplit(base_url)
    if (
        base_url != ALLOWED_BASE_URL
        or parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 5003
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise BflaManifestError(f"Disposable BFLA target must be exactly {ALLOWED_BASE_URL}.")
    return ALLOWED_BASE_URL


def validate_username(username: Any, run_id: str, suffix: str) -> str:
    """Validate a generated target name tied to this disposable run only."""
    expected = f"bfla-{validate_run_id(run_id)}-{suffix}"
    if username != expected:
        raise BflaManifestError("Target username does not match the declared disposable fixture.")
    return expected


def manifest_path(run_id: str, results_root: str | Path = "results/bfla-disposable") -> Path:
    """Return the public, non-secret manifest path for a run."""
    return Path(results_root) / validate_run_id(run_id) / "destructive-target-manifest.json"


def receipt_path(run_id: str, results_root: str | Path = "results/bfla-disposable") -> Path:
    """Return the public, non-secret execution receipt path for a run."""
    return Path(results_root) / validate_run_id(run_id) / "execution-receipt.json"


def teardown_receipt_path(run_id: str, results_root: str | Path = "results/bfla-disposable") -> Path:
    """Return the public, non-secret teardown receipt path for a run."""
    return Path(results_root) / validate_run_id(run_id) / "teardown-receipt.json"


def build_manifest(run_id: str) -> dict[str, Any]:
    """Build the immutable destructive scope for one disposable BFLA run."""
    run_id = validate_run_id(run_id)
    protected_victim = validate_username(f"bfla-{run_id}-victim", run_id, "victim")
    delete_control = validate_username(f"bfla-{run_id}-delete-control", run_id, "delete-control")
    project = expected_project_name(run_id)
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "run_id": run_id,
        "target": {
            "base_url": ALLOWED_BASE_URL,
            "compose_project": project,
            "service": "vampi",
        },
        "initialization": {
            "allowed_once": {
                "method": "GET",
                "path": "/createdb",
                "phase": "prepare-only",
            }
        },
        "destructive_targets": [
            {
                "id": "protected-victim",
                "username": protected_victim,
                "method": "DELETE",
                "path": f"/users/v1/{protected_victim}",
                "actor_role": "unprivileged-actor",
                "expected_status": 401,
                "must_exist_after_attempt": True,
            },
            {
                "id": "admin-delete-control",
                "username": delete_control,
                "method": "DELETE",
                "path": f"/users/v1/{delete_control}",
                "actor_role": "bootstrap-admin",
                "expected_status": 200,
                "must_not_exist_after_attempt": True,
            },
        ],
        "prohibitions": [
            f"any-target-other-than-{ALLOWED_BASE_URL}",
            "any-path-not-listed-above",
            "any-method-not-explicitly-listed",
            "reuse-of-roles_config.json",
            "reuse-of-ownership.csv",
            "docker-commands-targeting-vampi-week1",
            "unscoped-docker-prune",
        ],
    }


def _validate_target(target: Any, run_id: str) -> None:
    if not isinstance(target, dict):
        raise BflaManifestError("Disposable manifest target must be an object.")
    validate_base_url(target.get("base_url"))
    validate_project_name(target.get("compose_project"), run_id)
    if target.get("service") != "vampi":
        raise BflaManifestError("Disposable manifest service must be vampi.")


def _validate_target_entry(entry: Any, run_id: str, *, target_id: str, suffix: str, actor: str, expected_status: int) -> None:
    if not isinstance(entry, dict):
        raise BflaManifestError("Each destructive target must be an object.")
    username = validate_username(entry.get("username"), run_id, suffix)
    expected_path = f"/users/v1/{username}"
    if (
        entry.get("id") != target_id
        or entry.get("method") != "DELETE"
        or entry.get("path") != expected_path
        or entry.get("actor_role") != actor
        or entry.get("expected_status") != expected_status
    ):
        raise BflaManifestError("Disposable manifest destructive target differs from approved scope.")


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Validate one materialized manifest against the fixed destructive scope."""
    if not isinstance(manifest, dict):
        raise BflaManifestError("Disposable BFLA manifest must be an object.")
    if manifest.get("schema_version") != 1 or manifest.get("workflow") != WORKFLOW:
        raise BflaManifestError("Unsupported disposable BFLA manifest format.")
    run_id = validate_run_id(manifest.get("run_id"))
    expected = build_manifest(run_id)
    _validate_target(manifest.get("target"), run_id)
    targets = manifest.get("destructive_targets")
    if not isinstance(targets, list) or len(targets) != 2:
        raise BflaManifestError("Disposable manifest must contain exactly two declared targets.")
    _validate_target_entry(targets[0], run_id, target_id="protected-victim", suffix="victim", actor="unprivileged-actor", expected_status=401)
    _validate_target_entry(targets[1], run_id, target_id="admin-delete-control", suffix="delete-control", actor="bootstrap-admin", expected_status=200)
    if targets[0].get("must_exist_after_attempt") is not True or targets[1].get("must_not_exist_after_attempt") is not True:
        raise BflaManifestError("Disposable target survival expectations are invalid.")
    if manifest.get("initialization") != expected["initialization"]:
        raise BflaManifestError("Disposable manifest initialization differs from the one-time guarded reset.")
    if manifest.get("prohibitions") != expected["prohibitions"]:
        raise BflaManifestError("Disposable manifest prohibitions differ from the approved scope.")
    return manifest


def write_manifest(run_id: str, results_root: str | Path = "results/bfla-disposable") -> Path:
    """Create a credential-free public manifest only after strict construction."""
    manifest = validate_manifest(build_manifest(run_id))
    path = manifest_path(run_id, results_root)
    if path.exists() or path.is_symlink():
        raise BflaManifestError("Disposable manifest already exists for this immutable run ID.")
    write_redacted_json(path, manifest)
    return path


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate an existing public manifest without reading secrets."""
    return validate_manifest(read_json(path))
