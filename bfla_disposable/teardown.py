"""Project-scoped teardown for the disposable BFLA Docker environment."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from vampi_authz_lab.common import write_redacted_json

from .manifest import (
    ALLOWED_BASE_URL,
    BflaManifestError,
    teardown_receipt_path,
    validate_project_name,
    validate_run_directory,
    validate_run_id,
)
from .preflight import load_preflight_receipt
from .runner import secret_path


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an exact project-scoped Docker query or compose teardown command."""
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _assert_compose_file(compose_file: str | Path) -> Path:
    path = Path(compose_file).resolve()
    if path.name != "compose.yaml" or path.parent.name != "bfla-disposable" or not path.is_file():
        raise BflaManifestError("Teardown requires the fixed disposable compose.yaml path.")
    return path


def _week1_snapshot() -> dict[str, str | None]:
    result = _run(["docker", "inspect", "vampi-week1", "--format", "{{.Id}} {{.State.Status}}"])
    if result.returncode != 0:
        return {"id": None, "state": None}
    parts = result.stdout.strip().split(maxsplit=1)
    return {"id": parts[0] if parts else None, "state": parts[1] if len(parts) == 2 else None}


def _project_containers(compose_file: Path, project: str) -> list[str]:
    result = _run(["docker", "compose", "--project-name", project, "--file", str(compose_file), "ps", "-aq"])
    if result.returncode != 0:
        raise BflaExecutionError("Unable to inspect disposable project containers.")
    return [line for line in result.stdout.splitlines() if line]


def _project_volumes(project: str) -> list[str]:
    result = _run(["docker", "volume", "ls", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Name}}"])
    if result.returncode != 0:
        raise BflaExecutionError("Unable to inspect disposable project volumes.")
    return [line for line in result.stdout.splitlines() if line]


class BflaExecutionError(RuntimeError):
    """Raised when durable teardown evidence cannot be safely established."""


def teardown(
    run_id: str,
    project: str,
    run_dir: str | Path,
    compose_file: str | Path,
    results_root: str | Path = "results/bfla-disposable",
) -> dict[str, Any]:
    """Destroy only the matching Compose project, volume, and local secret run directory."""
    run_id = validate_run_id(run_id)
    validate_project_name(project, run_id)
    compose = _assert_compose_file(compose_file)
    directory = validate_run_directory(run_dir, run_id)
    try:
        preflight = load_preflight_receipt(run_id, project, results_root)
    except (BflaManifestError, OSError, ValueError):
        # Teardown remains available after an interrupted or damaged attestation so
        # a scoped disposable project cannot be stranded with test data.
        preflight = None
    if teardown_receipt_path(run_id, results_root).exists() or teardown_receipt_path(run_id, results_root).is_symlink():
        raise BflaManifestError("Disposable teardown receipt already exists for this immutable run ID.")
    before = _week1_snapshot()
    down = _run(["docker", "compose", "--project-name", project, "--file", str(compose), "down", "--volumes", "--remove-orphans"])
    containers = _project_containers(compose, project)
    volumes = _project_volumes(project)
    secret_removed = True
    try:
        if secret_path(directory).exists() or secret_path(directory).is_symlink():
            secret_path(directory).unlink()
        if directory.exists():
            shutil.rmtree(directory)
    except OSError:
        secret_removed = False
    after = _week1_snapshot()
    shared_unchanged = before == after and (
        preflight is None or before == preflight["shared_week1_before"]
    )
    complete = down.returncode == 0 and not containers and not volumes and secret_removed and shared_unchanged
    receipt = {
        "schema_version": 1,
        "workflow": "vampi-disposable-bfla-v1",
        "run_id": run_id,
        "compose_project": project,
        "service": "vampi",
        "target": ALLOWED_BASE_URL,
        "compose_down_exit_code": down.returncode,
        "remaining_project_containers": containers,
        "remaining_project_volumes": volumes,
        "persistent_test_data_removed": not containers and not volumes,
        "shared_week1_preflight": None if preflight is None else preflight["shared_week1_before"],
        "shared_week1_before": before,
        "shared_week1_after": after,
        "shared_week1_unchanged": shared_unchanged,
        "secret_run_directory_removed": secret_removed and not directory.exists(),
        "credential_or_response_bodies_exported": False,
        "preflight_receipt_available": preflight is not None,
        "status": "TEARDOWN_COMPLETE" if complete else "TEARDOWN_INCOMPLETE",
    }
    write_redacted_json(teardown_receipt_path(run_id, results_root), receipt)
    if not complete:
        raise BflaExecutionError("Disposable teardown is incomplete; see the credential-free teardown receipt.")
    return receipt
