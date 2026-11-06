"""Defense-in-depth guardrail and orchestrator for evaluation BFLA real execution.

This module wraps the existing ``disposable BFLA`` package with an additional
username-pattern guardrail that **rejects known fixture usernames** (userA,
userB, admin, …) and **accepts only disposable patterns**.  It never relaxes
the ``read_only/request_runner.py`` read-only restrictions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from authz_lab.common import read_json, write_redacted_json

# ── guardrail ────────────────────────────────────────────────────────

#: Usernames that belong to the shared Week 1 lab and must never be
#: targeted by a destructive operation.
KNOWN_FIXTURE_USERNAMES: frozenset[str] = frozenset({
    "admin",
    "admin2",
    "userA",
    "userB",
    "userC",
    "name1",
    "name2",
})

#: Acceptable disposable-username patterns.
#: • ``bfla_disposable_\d+`` — the established disposable-fixture pattern
#: • ``bfla-<run_id>-<suffix>`` — the pattern the existing infrastructure uses
DISPOSABLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"bfla_disposable_\d+"),
    re.compile(r"bfla-[a-z0-9]{8,32}-.+"),
)


class BflaGuardrailError(ValueError):
    """Raised when a BFLA target fails the defense-in-depth check."""


def assert_disposable_target(username: str) -> None:
    """Reject known fixture usernames; accept only disposable patterns.

    >>> assert_disposable_target("disposable BFLA_01")   # passes
    >>> assert_disposable_target("userA")                 # raises ValueError
    """
    if not isinstance(username, str) or not username:
        raise BflaGuardrailError("Username must be a non-empty string.")
    if username in KNOWN_FIXTURE_USERNAMES:
        raise BflaGuardrailError(
            f"Refusing known fixture username: {username}"
        )
    if not any(pattern.fullmatch(username) for pattern in DISPOSABLE_PATTERNS):
        raise BflaGuardrailError(
            f"Username does not match any disposable pattern: {username}"
        )


# ── findings builder ─────────────────────────────────────────────────

def _build_findings(
    run_id: str,
    execution_receipt: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Transform an execution receipt into a evaluation BFLA findings artifact."""
    ops = execution_receipt.get("operations", {})
    unprivileged = ops.get("unprivileged_delete", {})
    admin_ctrl = ops.get("admin_delete_control", {})

    targets = manifest.get("destructive_targets", [])
    victim_username = targets[0]["username"] if len(targets) > 0 else "unknown"
    control_username = targets[1]["username"] if len(targets) > 1 else "unknown"

    cases = [
        {
            "id": "non-admin-delete-victim",
            "actor": f"unprivileged (bfla-{run_id}-actor)",
            "target": victim_username,
            "pre_condition": "user exists (registered during prepare)",
            "delete_status": unprivileged.get("status"),
            "post_condition": "user still exists"
            if unprivileged.get("target_survived")
            else "user absent",
            "verdict": "DENIED"
            if unprivileged.get("target_survived")
            else "BFLA_CONFIRMED",
        },
    ]

    if admin_ctrl.get("status") is not None:
        cases.append(
            {
                "id": "admin-delete-control",
                "actor": "admin (bootstrap)",
                "target": control_username,
                "pre_condition": "user exists (registered during prepare)",
                "delete_status": admin_ctrl.get("status"),
                "post_condition": "user absent"
                if admin_ctrl.get("target_absent")
                else "user still exists",
                "verdict": "POSITIVE_CONTROL"
                if admin_ctrl.get("target_absent")
                else "INCONCLUSIVE",
            }
        )

    return {
        "schema_version": 1,
        "run_id": run_id,
        "week": 4,
        "finding_id": "W4-BFLA-01",
        "endpoint": "DELETE /users/v1/{username}",
        "guardrail_check": "assert_disposable_target passed for all targets",
        "cases": cases,
        "overall_verdict": execution_receipt.get("outcome", "INCONCLUSIVE"),
        "credential_or_response_bodies_exported": False,
    }


# ── orchestrator ─────────────────────────────────────────────────────

def _bfla_findings_path(
    run_id: str,
    results_root: str | Path = "results",
) -> Path:
    return Path(results_root) / "bfla_evaluation_findings.json"


def run_bfla_evaluation(
    run_id: str,
    *,
    results_root: str | Path = "results",
    bfla_results_root: str | Path = "results/bfla-disposable",
    compose_file: str | Path = "deploy/labs/vampi-bfla-disposable.compose.yaml",
) -> dict[str, Any]:
    """Orchestrate a full BFLA run with the defense-in-depth guardrail.

    This function:
    1. Builds the manifest and checks every target username with
       :func:`assert_disposable_target`.
    2. Delegates to the existing ``disposable BFLA`` infrastructure
       (create-manifest → preflight → prepare → execute).
    3. Transforms the execution receipt into ``bfla_evaluation_findings.json``.

    .. note::

       ``docker compose up`` and ``teardown`` must be run separately by the
       operator — this function handles the code-level stages only.  The
       operator is responsible for the Compose lifecycle.
    """
    from ..disposable.manifest import build_manifest, load_manifest, manifest_path

    # Build the manifest and run guardrail on every target username.
    manifest = build_manifest(run_id)
    for target in manifest.get("destructive_targets", []):
        assert_disposable_target(target["username"])

    # Load the execution receipt produced by disposable BFLA.runner.execute().
    receipt_file = Path(bfla_results_root) / run_id / "execution-receipt.json"
    if not receipt_file.is_file():
        raise BflaGuardrailError(
            f"Execution receipt not found at {receipt_file}. "
            "Run the disposable BFLA workflow first "
            "(create-manifest → preflight → compose up → prepare → execute → teardown)."
        )
    execution_receipt = read_json(receipt_file)

    # Load the manifest for username details.
    manifest_file = manifest_path(run_id, bfla_results_root)
    saved_manifest = load_manifest(manifest_file)

    # Re-check guardrail on the saved manifest targets.
    for target in saved_manifest.get("destructive_targets", []):
        assert_disposable_target(target["username"])

    # Build and write the evaluation findings artifact.
    findings = _build_findings(run_id, execution_receipt, saved_manifest)
    extended_file = Path(bfla_results_root) / run_id / "extended-state-receipt.json"
    if extended_file.is_file():
        findings["extended_state_findings"] = read_json(extended_file).get("operations", {})
    output_path = _bfla_findings_path(run_id, results_root)
    write_redacted_json(output_path, findings)
    return findings
