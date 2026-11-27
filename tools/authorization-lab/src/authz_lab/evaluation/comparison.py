"""final comparison builder — three-method final comparison.

The manual column distinguishes missing functional evidence from intentional
absence of a stopwatch metric. Completed observations with ``—`` timing remain
valid security evidence and are reported as ``COMPLETED_NO_TIMING``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from authz_lab.common import read_json, write_redacted_json
from authz_lab.evaluation.timing import TimingEvidence, load_timing_evidence, _validate_timing_payload


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
    try:
        lines = worksheet.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return _pending_manual_result("Worksheet could not be read.")
    for line in lines:
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
        if not status.isdigit() or not 100 <= int(status) <= 599 or not finding
    ]
    if incomplete:
        return _pending_manual_result("Worksheet has incomplete observed status or finding notes.")

    confirmed = sum(
        1 for _status, finding, _timing in rows.values()
        if "BOLA confirmed" in finding
    )
    timings = [timing for _status, _finding, timing in rows.values()]
    numeric_timings: list[float] = []
    invalid_timing = False
    for timing in timings:
        if timing in {"", "—", "-"}:
            continue
        try:
            value = float(timing)
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid timing")
            numeric_timings.append(value)
        except ValueError:
            invalid_timing = True

    if (not invalid_timing and numeric_timings and len(numeric_timings) == len(rows)
            and math.isfinite(sum(numeric_timings))):
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
        "note": "Manual functional evidence is complete; stopwatch timing is invalid or incomplete." if invalid_timing else "Manual functional evidence is complete; stopwatch timing was not fully measured.",
    }


def _load_verification_counts(source: Path | None) -> tuple[int | None, int | None, int | None]:
    """Count supplied observations; absence or malformed records remain unknown."""
    if source is None:
        return None, None, None
    try:
        records = read_json(source)
    except (ValueError, OSError):
        return None, None, None
    if not isinstance(records, list) or not records or any(
        not isinstance(item, dict) or not isinstance(item.get("outcome"), str)
        or item["outcome"] not in {
            "CONFIRMED_USER_TO_USER_BOLA", "CONFIRMED_USER_TO_ADMIN_BOLA",
            "POLICY_DEPENDENT_ADMIN_ACCESS", "CONFIRMED_EXCESSIVE_DATA_EXPOSURE",
            "NOT_REPRODUCED",
        } for item in records
    ):
        return None, None, None
    return tuple(sum(item["outcome"] == outcome for item in records) for outcome in (
        "CONFIRMED_USER_TO_USER_BOLA", "CONFIRMED_USER_TO_ADMIN_BOLA",
        "POLICY_DEPENDENT_ADMIN_ACCESS",
    ))


def build_final_comparison(
    bfla_findings: dict[str, Any] | None,
    zap_report: dict[str, Any] | None,
    manual_worksheet_path: str | Path = "results/manual_verification_worksheet.md",
    *,
    timing_evidence: TimingEvidence | None = None,
    script_timing_path: str | Path | None = None,
    verification_path: str | Path | None = None,
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
        Optional legacy timing path, validated with the same strict loader.
    verification_path : path or None
        Functional observations, independent of stopwatch evidence. Adjacent
        legacy discovery remains supported, without asserting cohort alignment.
    """
    # ── custom script column ──
    if timing_evidence is None and script_timing_path is not None:
        timing_evidence = load_timing_evidence(
            results_root=Path(script_timing_path).parent, timing_file=script_timing_path,
        )
    if timing_evidence is not None and timing_evidence.status == "AVAILABLE":
        validated = _validate_timing_payload({
            "status": "MEASURED", "elapsed_ms": timing_evidence.elapsed_ms,
            "case_count": timing_evidence.case_count,
        }, timing_evidence.source)
        if validated.status != "AVAILABLE":
            timing_evidence = validated
    measured_case_count = (
        timing_evidence.case_count if timing_evidence is not None
        and timing_evidence.status == "AVAILABLE" else None
    )
    # Legacy adjacent discovery is local to the selected artifact directory.
    # Never search its parent and accidentally mix independent runs.
    source = Path(verification_path) if verification_path is not None else None
    if source is None and timing_evidence is not None and timing_evidence.source is not None:
        source = next((timing_evidence.source.parent / name for name in (
            "manual_verification.json", "week3_manual_verification.json"
        ) if (timing_evidence.source.parent / name).is_file()), None)
    counts = _load_verification_counts(source)
    confirmed_bola_count, confirmed_user_to_admin_bola, policy_dependent_admin_access = counts

    script_data: dict[str, Any] = {
        "status": "TIMING_NOT_AVAILABLE",
        "case_count": measured_case_count,
        "confirmed_user_to_user_bola": confirmed_bola_count,
        "confirmed_user_to_admin_bola": confirmed_user_to_admin_bola,
        "policy_dependent_admin_access": policy_dependent_admin_access,
        "hidden_200_data_exposure": None,
        "functional_status": "AVAILABLE" if counts[0] is not None else "UNAVAILABLE",
        "verification_source": str(source) if counts[0] is not None else None,
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
    elif isinstance(zap_report, dict) and zap_report.get("status") == "NOT_RUN":
        zap_data = {
            "status": "NOT_RUN",
            "finding_count": None,
            "reason": zap_report.get("reason", "Unknown reason."),
        }
    elif isinstance(zap_report, dict) and str(zap_report.get("status", "")).startswith("BOOTSTRAP_"):
        zap_data = {
            "status": "NOT_RUN",
            "finding_count": None,
            "reason": "ZAP Desktop authentication bootstrap is pending operator authentication and traffic quiescence; no scan was run.",
        }
    elif (isinstance(zap_report, dict) and zap_report.get("status") == "COMPLETED"
          and type(zap_report.get("scan_result_count")) is int
          and zap_report["scan_result_count"] >= 0
          and isinstance(zap_report.get("unauthorized_access_findings"), list)
          and all(isinstance(row, dict) for row in zap_report["unauthorized_access_findings"])
          and len(zap_report["unauthorized_access_findings"]) <= zap_report["scan_result_count"]):
        zap_data = {
            "status": "COMPLETED",
            "finding_count": zap_report.get("scan_result_count"),
            "unauthorized_access_count": len(
                zap_report.get("unauthorized_access_findings", [])
            ),
            "comparison_with_known_bola": zap_report.get(
                "comparison_with_known_bola"
            ),
        }

    else:
        zap_data = {"status": "INVALID", "finding_count": None,
                    "reason": "Missing, unsupported, or inconsistent ZAP completion evidence."}

    # ── BFLA column (new in final) ──
    if bfla_findings is None:
        bfla_data: dict[str, Any] = {
            "status": "NOT_RUN",
            "verdict": None,
        }
    elif (isinstance(bfla_findings, dict)
          and bfla_findings.get("overall_verdict") in {
              "DENIED_CONTROL", "BFLA_CONFIRMED_DESTRUCTIVE", "INCONCLUSIVE"}
          and bfla_findings.get("status", "EXECUTED") == "EXECUTED"
          and isinstance(bfla_findings.get("cases"), list) and bfla_findings["cases"]
          and all(isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"] and row.get("verdict") in {
              "DENIED", "BFLA_CONFIRMED", "POSITIVE_CONTROL", "INCONCLUSIVE"
          } for row in bfla_findings["cases"])
          and len({row["id"] for row in bfla_findings["cases"]}) == len(bfla_findings["cases"])
          and (bfla_findings["overall_verdict"] == "INCONCLUSIVE" or
               (bfla_findings["overall_verdict"] == "DENIED_CONTROL"
                and {row["verdict"] for row in bfla_findings["cases"]} == {"DENIED", "POSITIVE_CONTROL"}) or
               (bfla_findings["overall_verdict"] == "BFLA_CONFIRMED_DESTRUCTIVE"
                and any(row["verdict"] == "BFLA_CONFIRMED" for row in bfla_findings["cases"])))):
        bfla_data = {
            "status": "EXECUTED",
            "verdict": bfla_findings.get("overall_verdict"),
            "finding_id": bfla_findings.get("finding_id"),
            "case_count": len(bfla_findings.get("cases", [])),
            "endpoint": bfla_findings.get("endpoint"),
        }

    else:
        bfla_data = {"status": "INVALID", "verdict": None, "case_count": None}

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
