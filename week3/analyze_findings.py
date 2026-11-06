"""Create conservative Week 3 classifications from verified local-lab evidence."""

from __future__ import annotations

from typing import Any


def classify_findings(
    verification: list[dict[str, Any]], endpoint_inventory: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return findings without promoting unexecuted candidates to confirmed defects."""
    user_to_user = [
        item
        for item in verification
        if item["outcome"] in {"CONFIRMED_USER_TO_USER_BOLA", "CONFIRMED_USER_TO_ADMIN_BOLA"}
    ]
    admin_access = [item for item in verification if item["outcome"] == "POLICY_DEPENDENT_ADMIN_ACCESS"]
    findings: list[dict[str, Any]] = [
        {
            "finding_id": "W3-01",
            "classification": "BOLA",
            "status": "CONFIRMED",
            "severity": "Medium",
            "endpoint": "/books/v1/{book_title}",
            "method": "GET",
            "impact": "Read: a non-owner regular user received another fixture owner's secret (including User->User and User->Admin).",
            "exposure_mechanism": "Direct full sensitive-field exposure at $.secret.",
            "evidence_count": len(user_to_user),
            "evidence": [
                {
                    "actor_role": item["actor_role"],
                    "owner_role": item["owner_role"],
                    "access_direction": item.get("access_direction", "USER_TO_USER"),
                    "fixture_id": item["fixture_id"],
                    "status_code": item["status_code"],
                    "secret_matches_fresh_owner_baseline": item["secret_matches_fresh_owner_baseline"],
                }
                for item in user_to_user
            ],
            "recommendation": "Constrain book lookup by the authenticated subject and return a consistent denial/hidden response for non-owners.",
            "scope_note": "Severity is Medium for this isolated teaching lab. Production severity depends on the sensitivity and business value of the secret data.",
        },
        {
            "finding_id": "W3-02",
            "classification": "ADMIN_ACCESS_POLICY",
            "status": "POLICY_DEPENDENT",
            "severity": "Not rated",
            "endpoint": "/books/v1/{book_title}",
            "method": "GET",
            "impact": "Administrator token read another owner's book fixture (Admin->User or Admin->Admin).",
            "exposure_mechanism": "Response matched the fresh owner baseline at $.secret.",
            "evidence_count": len(admin_access),
            "evidence": [
                {
                    "actor_role": item["actor_role"],
                    "owner_role": item["owner_role"],
                    "access_direction": item.get("access_direction", "ADMIN_TO_USER"),
                    "fixture_id": item["fixture_id"],
                    "status_code": item["status_code"],
                }
                for item in admin_access
            ],
            "recommendation": "Document whether administrators are intended to bypass object ownership checks before treating this behavior as a defect.",
            "scope_note": "Not an independent confirmed issue without an explicit product authorization policy.",
        },
    ]

    bfla_candidates = [
        item
        for item in endpoint_inventory
        if item.get("is_bfla_candidate") and item.get("state_changing") and item.get("method") == "DELETE"
    ]
    for endpoint in bfla_candidates:
        findings.append(
            {
                "finding_id": "W3-03",
                "classification": "BFLA",
                "status": "NOT_EXECUTED",
                "severity": "Not rated",
                "endpoint": endpoint["path"],
                "method": endpoint["method"],
                "impact": "Potential administrative user deletion operation.",
                "exposure_mechanism": "OpenAPI operation metadata marks the function as admin-related.",
                "evidence_count": 0,
                "evidence": [],
                "recommendation": "Use a disposable fixture and explicit state-changing authorization before testing this candidate.",
                "scope_note": "Excluded from Week 3 because the safe runner blocks destructive operations.",
            }
        )

    debug_candidates = [
        item
        for item in endpoint_inventory
        if (
            item.get("is_excessive_data_exposure_candidate")
            or (item.get("is_bfla_candidate") and not item.get("state_changing") and item.get("method") == "GET")
        )
    ]
    for endpoint in debug_candidates:
        verified_debug = [
            item
            for item in verification
            if item.get("outcome") == "CONFIRMED_EXCESSIVE_DATA_EXPOSURE"
            and item.get("endpoint") == endpoint["path"]
        ]
        findings.append(
            {
                "finding_id": "W3-04",
                "classification": "EXCESSIVE_DATA_EXPOSURE",
                "status": "CONFIRMED" if verified_debug else "NOT_EXECUTED",
                "severity": "High" if verified_debug else "Not rated",
                "endpoint": endpoint["path"],
                "method": endpoint["method"],
                "impact": "Unauthenticated/unprivileged access to debug endpoint dumps all user plaintext passwords and admin flags.",
                "exposure_mechanism": "Direct credential dump at $.users[*].password and $.users[*].admin.",
                "evidence_count": len(verified_debug),
                "evidence": [
                    {
                        "actor_role": item["actor_role"],
                        "endpoint": item["endpoint"],
                        "status_code": item["status_code"],
                        "user_record_count": item.get("user_record_count", 0),
                        "exposes_plaintext_passwords_and_admin_flags": item.get(
                            "exposes_plaintext_passwords_and_admin_flags", False
                        ),
                    }
                    for item in verified_debug
                ],
                "recommendation": "Disable debug endpoints in production or restrict response serialization so plaintext secrets and privilege flags are never returned.",
                "scope_note": "Confirmed only when live independent verification proves non-empty user credential exposure.",
            }
        )
    return findings


def build_comparison(script_timing: dict[str, Any], verification: list[dict[str, Any]], zap: dict[str, Any]) -> dict[str, Any]:
    """Build an honest comparison: only measured columns receive measured values."""
    user_confirmed = sum(item.get("outcome") == "CONFIRMED_USER_TO_USER_BOLA" for item in verification)
    user_to_admin_confirmed = sum(item.get("outcome") == "CONFIRMED_USER_TO_ADMIN_BOLA" for item in verification)
    policy_dependent = sum(item.get("outcome") == "POLICY_DEPENDENT_ADMIN_ACCESS" for item in verification)
    return {
        "comparison_scope": {
            "target": "http://127.0.0.1:5000",
            "script_total_cases": script_timing["case_count"],
            "manual_sample_cases": 7,
            "normalization_note": "Finding totals must be compared on the same selected endpoint subset; automated cases and 7 manual samples are not directly interchangeable.",
        },
        "custom_script": {
            "status": "MEASURED",
            "elapsed_ms": script_timing["elapsed_ms"],
            "case_count": script_timing["case_count"],
            "confirmed_user_to_user_bola": user_confirmed,
            "confirmed_user_to_admin_bola": user_to_admin_confirmed,
            "policy_dependent_admin_access": policy_dependent,
            "hidden_200_data_exposure": "Yes; fresh owner-baseline secret comparison.",
        },
        "manual_postman_or_burp": {
            "status": "PENDING_HUMAN_MEASUREMENT",
            "sample_case_count": 7,
            "elapsed_minutes": None,
            "confirmed_findings": None,
            "note": "Use results/week3_manual_worksheet.md and a real stopwatch. Automated curl timing is not substituted for a human-tool measurement.",
        },
        "owasp_zap": zap,
    }
