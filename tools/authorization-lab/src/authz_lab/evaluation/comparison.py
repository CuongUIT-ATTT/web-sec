"""final comparison builder — three-method final comparison.

The manual column distinguishes missing functional evidence from intentional
absence of a stopwatch metric. Completed observations with ``—`` timing remain
valid security evidence and are reported as ``COMPLETED_NO_TIMING``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from authz_lab.common import read_json, write_redacted_json
from authz_lab.evaluation.timing import TimingEvidence


EXPECTED_MANUAL_CASE_IDS = frozenset({f"M-{number:02d}" for number in range(1, 8)})


def _pending_manual_result(note: str) -> dict[str, Any]:
    return {
        "status": "PENDING_HUMAN_MEASUREMENT",
        "sample_case_count": 7,
        "elapsed_minutes": None,
        "confirmed_findings": None,
        "note": note,
    }


def _parse_manual_worksheet(path: str | Path) -> dict[str, Any]:
    """Parse completed functional observations without requiring a stopwatch.

    A completed row must contain the exact sample ID, observed HTTP status, and
    a non-empty finding/notes cell. Timing may be numeric or the explicit ``—``
    marker for intentionally unmeasured human workflow time.
    """
    worksheet = Path(path)
    if not worksheet.is_file():
        return _pending_manual_result(
            "Worksheet not found. Record all seven functional observations before comparison."
        )

    rows: dict[str, tuple[str, str, str]] = {}
    for line in worksheet.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7 or cells[0] not in EXPECTED_MANUAL_CASE_IDS:
            continue
        case_id, _endpoint, _auth, _expected, observed_status, finding, timing = cells
        if case_id in rows:
            return _pending_manual_result("Worksheet has duplicate manual case IDs.")
        rows[case_id] = (observed_status, finding, timing)

    if set(rows) != EXPECTED_MANUAL_CASE_IDS:
        return _pending_manual_result(
            "Worksheet does not contain all seven completed manual case IDs."
        )
    incomplete = [
        case_id for case_id, (status, finding, _timing) in rows.items()
        if not status or not finding
    ]
    if incomplete:
        return _pending_manual_result("Worksheet has incomplete observed status or finding notes.")

    confirmed = sum(
        1 for _status, finding, _timing in rows.values()
        if "BOLA confirmed" in finding
    )
    timings = [timing for _status, _finding, timing in rows.values()]
    numeric_timings: list[float] = []
    for timing in timings:
        if timing in {"", "—", "-"}:
            continue
        try:
            numeric_timings.append(float(timing))
        except ValueError:
            return _pending_manual_result("Worksheet contains an invalid manual timing value.")

    if numeric_timings and len(numeric_timings) == len(rows):
        return {
            "status": "COMPLETED",
            "sample_case_count": 7,
            "filled_case_count": 7,
            "confirmed_findings": confirmed,
            "elapsed_minutes": sum(numeric_timings) / 60,
            "note": "Manual functional evidence and stopwatch measurements are complete.",
        }
    return {
        "status": "COMPLETED_NO_TIMING",
        "sample_case_count": 7,
        "filled_case_count": 7,
        "confirmed_findings": confirmed,
        "elapsed_minutes": None,
        "note": "Manual functional evidence is complete; stopwatch timing was intentionally not measured.",
    }


def _load_verification_counts(timing_source: Path | None) -> tuple[int, int, int]:
    """Read directional BOLA counts from verification artifact adjacent to timing_source."""
    confirmed_bola_count = 2
    confirmed_user_to_admin_bola = 0
    policy_dependent_admin_access = 0
    if timing_source is None:
        return confirmed_bola_count, confirmed_user_to_admin_bola, policy_dependent_admin_access
    parent = timing_source.parent
    for candidate_name in ("manual_verification.json", "week3_manual_verification.json"):
        verification_file = parent / candidate_name
        if not verification_file.is_file() and parent.parent != parent:
            verification_file = parent.parent / candidate_name
        if verification_file.is_file():
            verif_records = read_json(verification_file)
            if isinstance(verif_records, list):
                confirmed_bola_count = sum(
                    item.get("outcome") == "CONFIRMED_USER_TO_USER_BOLA"
                    for item in verif_records
                    if isinstance(item, dict)
                )
                confirmed_user_to_admin_bola = sum(
                    item.get("outcome") == "CONFIRMED_USER_TO_ADMIN_BOLA"
                    for item in verif_records
                    if isinstance(item, dict)
                )
                policy_dependent_admin_access = sum(
                    item.get("outcome") == "POLICY_DEPENDENT_ADMIN_ACCESS"
                    for item in verif_records
                    if isinstance(item, dict)
                )
            break
    return confirmed_bola_count, confirmed_user_to_admin_bola, policy_dependent_admin_access


def build_final_comparison(
    bfla_findings: dict[str, Any] | None,
    zap_report: dict[str, Any] | None,
    manual_worksheet_path: str | Path = "results/manual_verification_worksheet.md",
    *,
    timing_evidence: TimingEvidence | None = None,
    script_timing_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the final three-method comparison for final.

    Parameters
    ----------
    bfla_findings : dict or None
        The ``bfla_evaluation_findings.json`` content, or None if not run.
    zap_report : dict or None
        The ``zap_access_control_report.json`` content, or None if not run.
    manual_worksheet_path : path
        Path to the manual worksheet markdown file.
    timing_evidence : TimingEvidence or None
        Validated automated pipeline timing, if a timing artifact is available.
    script_timing_path : path or None
        Optional legacy timing path fallback.
    """
    # ── custom script column ──
    measured_case_count = 12
    confirmed_bola_count = 2
    confirmed_user_to_admin_bola = 0
    policy_dependent_admin_access = 0

    if timing_evidence is None and script_timing_path and Path(script_timing_path).is_file():
        timing_path_obj = Path(script_timing_path)
        timing = read_json(timing_path_obj)
        case_count_val = timing.get("case_count") if isinstance(timing.get("case_count"), int) else 12
        timing_evidence = TimingEvidence(
            status="AVAILABLE",
            source=timing_path_obj,
            elapsed_ms=timing.get("elapsed_ms"),
            case_count=case_count_val,
        )

    if timing_evidence is not None and timing_evidence.status == "AVAILABLE":
        if isinstance(timing_evidence.case_count, int):
            measured_case_count = timing_evidence.case_count
        (
            confirmed_bola_count,
            confirmed_user_to_admin_bola,
            policy_dependent_admin_access,
        ) = _load_verification_counts(timing_evidence.source)

    script_data: dict[str, Any] = {
        "status": "TIMING_NOT_AVAILABLE",
        "case_count": measured_case_count,
        "confirmed_user_to_user_bola": confirmed_bola_count,
        "confirmed_user_to_admin_bola": confirmed_user_to_admin_bola,
        "policy_dependent_admin_access": policy_dependent_admin_access,
        "hidden_200_data_exposure": "Yes; fresh owner-baseline secret comparison.",
        "elapsed_ms": None,
    }
    if timing_evidence is not None and timing_evidence.status == "AVAILABLE":
        script_data.update(
            status="MEASURED",
            case_count=measured_case_count,
            elapsed_ms=timing_evidence.elapsed_ms,
            timing_source=str(timing_evidence.source),
        )
    elif timing_evidence is not None:
        script_data["timing_status"] = timing_evidence.status
        script_data["note"] = timing_evidence.reason
    else:
        script_data["timing_status"] = "UNAVAILABLE"
        script_data["note"] = "Automated timing evidence was not supplied."

    # ── manual column ──
    manual_data = _parse_manual_worksheet(manual_worksheet_path)

    # ── ZAP column ──
    if zap_report is None:
        zap_data: dict[str, Any] = {
            "status": "NOT_RUN",
            "finding_count": None,
            "reason": "ZAP Access Control scan was not executed.",
        }
    elif zap_report.get("status") == "NOT_RUN":
        zap_data = {
            "status": "NOT_RUN",
            "finding_count": None,
            "reason": zap_report.get("reason", "Unknown reason."),
        }
    elif zap_report.get("status") == "BOOTSTRAP_REQUIRES_OPERATOR_AUTH_AND_QUIESCE":
        zap_data = {
            "status": "NOT_RUN",
            "finding_count": None,
            "reason": "ZAP Desktop authentication bootstrap is pending operator authentication and traffic quiescence; no scan was run.",
        }
    else:
        zap_data = {
            "status": zap_report.get("status", "COMPLETED"),
            "finding_count": zap_report.get("scan_result_count"),
            "unauthorized_access_count": len(
                zap_report.get("unauthorized_access_findings", [])
            ),
            "comparison_with_known_bola": zap_report.get(
                "comparison_with_known_bola"
            ),
        }

    # ── BFLA column (new in final) ──
    if bfla_findings is None:
        bfla_data: dict[str, Any] = {
            "status": "NOT_RUN",
            "verdict": None,
        }
    else:
        bfla_data = {
            "status": "EXECUTED",
            "verdict": bfla_findings.get("overall_verdict"),
            "finding_id": bfla_findings.get("finding_id"),
            "case_count": len(bfla_findings.get("cases", [])),
            "endpoint": bfla_findings.get("endpoint"),
        }

    return {
        "comparison_scope": {
            "target": "http://127.0.0.1:5000",
            "script_total_cases": measured_case_count,
            "manual_sample_cases": 7,
            "bfla_disposable_target": "http://127.0.0.1:5003",
            "normalization_note": (
                f"Finding totals must be compared on the same selected "
                f"endpoint subset; {measured_case_count} automated cases, 7 manual samples, "
                f"and BFLA disposable cases are not directly interchangeable."
            ),
        },
        "custom_script": script_data,
        "manual_postman_or_burp": manual_data,
        "owasp_zap": zap_data,
        "bfla_disposable": bfla_data,
    }


def write_comparison(
    comparison: dict[str, Any],
    output_path: str | Path = "results/authorization_comparison_final.json",
) -> Path:
    """Write the comparison artifact with redaction checks."""
    path = Path(output_path)
    write_redacted_json(path, comparison)
    return path


build_week4_comparison = build_final_comparison
