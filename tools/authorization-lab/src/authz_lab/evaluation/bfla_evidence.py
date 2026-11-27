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
    # Schema v1 producer currently omits proof. Never infer it from outcome,
    # HTTP success, or the fact that prepare once registered a target.
    def mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    receipt = mapping(execution_receipt)
    manifest = mapping(manifest)
    ops = mapping(receipt.get("operations"))
    targets = manifest.get("destructive_targets")
    targets = targets if isinstance(targets, list) else []
    context_valid = (
        receipt.get("run_id") == run_id
        and manifest.get("run_id") == run_id
        and type(receipt.get("schema_version")) is int
        and receipt.get("schema_version") == 1
        and receipt.get("workflow") == "vampi-disposable-bfla-v1"
        and receipt.get("target") == "http://127.0.0.1:5003"
    )

    def case(index: int, key: str, admin: bool) -> dict[str, Any]:
        operation = mapping(ops.get(key))
        target = mapping(targets[index]) if len(targets) > index else {}
        username = target.get("username")
        expected_username = f"bfla-{run_id}-" + ("delete-control" if admin else "victim")
        path = f"/users/v1/{expected_username}"
        proof = mapping(operation.get("proof"))
        baseline = mapping(proof.get("baseline"))
        principal = mapping(proof.get("principal"))
        post = mapping(proof.get("postcondition"))
        status = operation.get("status")
        valid = (
            context_valid and username == expected_username and target.get("path") == path
            and type(status) is int and 100 <= status <= 599
            and baseline.get("status") == 200 and type(baseline.get("status")) is int
            and baseline.get("username") == username and baseline.get("fresh") is True
            and principal.get("status") == 200 and type(principal.get("status")) is int
            and principal.get("username") == ("admin" if admin else f"bfla-{run_id}-actor")
            and principal.get("admin") is admin
            and post.get("username") == username and post.get("path") == path
        )
        state = operation.get("target_absent" if admin else "target_survived")
        absent = state is (True if admin else False)
        exists = state is (False if admin else True)
        absent = valid and absent and type(post.get("status")) is int and post.get("status") == 404
        exists = valid and exists and type(post.get("status")) is int and post.get("status") == 200
        verdict = "INCONCLUSIVE"
        if absent and (not admin or status == 200):
            verdict = "POSITIVE_CONTROL" if admin else "BFLA_CONFIRMED"
        elif exists and not admin and status == target.get("expected_status") == 401:
            verdict = "DENIED"
        return {
            "id": "admin-delete-control" if admin else "non-admin-delete-victim",
            "actor": "admin (bootstrap)" if admin else f"unprivileged (bfla-{run_id}-actor)",
            "target": username if isinstance(username, str) else "unknown",
            "pre_condition": "fresh user profile verified" if valid else "unverified",
            "delete_status": status if type(status) is int else None,
            "post_condition": "user absent" if absent else "user still exists" if exists else "unknown",
            "verdict": verdict,
        }

    cases = [case(0, "unprivileged_delete", False)]
    if mapping(ops.get("admin_delete_control")).get("status") is not None:
        cases.append(case(1, "admin_delete_control", True))
    derived = "INCONCLUSIVE"
    if cases[0]["verdict"] == "BFLA_CONFIRMED":
        derived = "BFLA_CONFIRMED_DESTRUCTIVE"
    elif (cases[0]["verdict"] == "DENIED" and len(cases) == 2
          and cases[1]["verdict"] == "POSITIVE_CONTROL"):
        derived = "DENIED_CONTROL"
    # A contradictory producer summary invalidates classification, even if a
    # subset of fields appears positive. Keep observations, never trust summary.
    if receipt.get("outcome") != derived:
        derived = "INCONCLUSIVE"
        for item in cases:
            item["verdict"] = "INCONCLUSIVE"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "week": 4,
        "finding_id": "W4-BFLA-01",
        "endpoint": "DELETE /users/v1/{username}",
        "guardrail_check": "assert_disposable_target passed for all targets",
        "cases": cases,
        "overall_verdict": derived,
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
