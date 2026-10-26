"""Week 4 comparison builder — three-method final comparison.

The manual column distinguishes missing functional evidence from intentional
absence of a stopwatch metric. Completed observations with ``—`` timing remain
valid security evidence and are reported as ``COMPLETED_NO_TIMING``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vampi_authz_lab.common import read_json, write_redacted_json


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


def build_week4_comparison(
    bfla_findings: dict[str, Any] | None,
    zap_report: dict[str, Any] | None,
    manual_worksheet_path: str | Path = "results/week3_manual_worksheet.md",
    *,
    script_timing_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the final three-method comparison for Week 4.

    Parameters
    ----------
    bfla_findings : dict or None
        The ``week4_bfla_findings.json`` content, or None if not run.
    zap_report : dict or None
        The ``zap_access_control_report.json`` content, or None if not run.
    manual_worksheet_path : path
        Path to the manual worksheet markdown file.
    script_timing_path : path or None
        Path to ``week3_script_timing.json`` for automated pipeline timing.
    """
    # ── custom script column ──
    script_data: dict[str, Any] = {
        "status": "MEASURED",
        "case_count": 12,
        "confirmed_user_to_user_bola": 2,
        "hidden_200_data_exposure": "Yes; fresh owner-baseline secret comparison.",
    }
    if script_timing_path and Path(script_timing_path).is_file():
        timing = read_json(script_timing_path)
        script_data["elapsed_ms"] = timing.get("elapsed_ms")
    else:
        # Use the known rerun timing.
        script_data["elapsed_ms"] = None
        script_data["note"] = "Timing from latest rerun not loaded."

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

    # ── BFLA column (new in Week 4) ──
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
            "script_total_cases": 12,
            "manual_sample_cases": 7,
            "bfla_disposable_target": "http://127.0.0.1:5003",
            "normalization_note": (
                "Finding totals must be compared on the same selected "
                "endpoint subset; 12 automated cases, 7 manual samples, "
                "and BFLA disposable cases are not directly interchangeable."
            ),
        },
        "custom_script": script_data,
        "manual_postman_or_burp": manual_data,
        "owasp_zap": zap_data,
        "bfla_disposable": bfla_data,
    }


def write_comparison(
    comparison: dict[str, Any],
    output_path: str | Path = "results/week4_comparison_final.json",
) -> Path:
    """Write the comparison artifact with redaction checks."""
    path = Path(output_path)
    write_redacted_json(path, comparison)
    return path
