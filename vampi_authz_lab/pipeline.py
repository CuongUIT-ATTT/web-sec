"""In-process orchestration for safe Week 2 and Week 3 local-lab workflows."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from week2.matrix_builder import build_test_matrix, load_ownership
from week2.request_runner import ALLOWED_BASE_URL, load_roles_config, preflight, run_all_tests, validate_base_url
from week2.response_comparator import analyze_all
from week2.spec_parser import extract_endpoints, load_spec
from week3.analyze_findings import build_comparison, classify_findings
from week3.manual_verifier import independently_verify_books

from .common import read_json, write_redacted_json


def validate_inputs(spec_path: Path, roles_path: Path, ownership_path: Path) -> dict[str, Any]:
    """Validate local input files without making any network request or printing secrets."""
    spec = load_spec(spec_path)
    endpoints = extract_endpoints(spec)
    roles = load_roles_config(roles_path)
    fixtures = load_ownership(ownership_path)
    return {
        "spec_path": str(spec_path),
        "roles_path": str(roles_path),
        "ownership_path": str(ownership_path),
        "operation_count": len(endpoints),
        "role_names": sorted(roles),
        "fixture_count": len(fixtures),
        "ownership_input_format": "CSV",
    }


def run_pipeline(
    spec_path: Path,
    roles_path: Path,
    ownership_path: Path,
    output_dir: Path,
    base_url: str = ALLOWED_BASE_URL,
) -> dict[str, Any]:
    """Run the existing safe read-only pipeline and write only redacted artifacts."""
    validate_base_url(base_url)
    spec = load_spec(spec_path)
    endpoints = extract_endpoints(spec)
    roles_config = load_roles_config(roles_path)
    fixtures = load_ownership(ownership_path)
    matrix = build_test_matrix(endpoints, fixtures, sorted(roles_config))

    output_dir.mkdir(parents=True, exist_ok=True)
    write_redacted_json(output_dir / "endpoint_inventory.json", endpoints)
    write_redacted_json(output_dir / "ownership_map.json", fixtures)
    write_redacted_json(output_dir / "test_matrix.json", matrix)

    preflight_result = preflight(roles_config, fixtures, base_url)
    raw_results = run_all_tests(matrix, roles_config, base_url)
    final_results = analyze_all(raw_results)
    write_redacted_json(output_dir / "preflight.json", preflight_result)
    write_redacted_json(output_dir / "raw_results.json", raw_results)
    write_redacted_json(output_dir / "final_report.json", final_results)
    return {
        "endpoints": endpoints,
        "fixtures": fixtures,
        "roles_config": roles_config,
        "matrix": matrix,
        "preflight": preflight_result,
        "raw_results": raw_results,
        "final_results": final_results,
    }


def run_verification(
    spec_path: Path,
    roles_path: Path,
    ownership_path: Path,
    output_dir: Path,
    base_url: str = ALLOWED_BASE_URL,
) -> dict[str, Any]:
    """Independently verify known book fixtures without rerunning the Week 2 matrix."""
    validate_base_url(base_url)
    spec = load_spec(spec_path)
    endpoints = extract_endpoints(spec)
    roles_config = load_roles_config(roles_path)
    fixtures = load_ownership(ownership_path)
    verification = independently_verify_books(roles_config, fixtures, base_url)
    findings = classify_findings(verification, endpoints)

    write_redacted_json(output_dir / "week3_manual_verification.json", verification)
    write_redacted_json(output_dir / "week3_findings.json", findings)
    return {"endpoints": endpoints, "fixtures": fixtures, "verification": verification, "findings": findings}


def run_week3_workflow(
    spec_path: Path,
    roles_path: Path,
    ownership_path: Path,
    output_dir: Path,
    base_url: str = ALLOWED_BASE_URL,
) -> dict[str, Any]:
    """Time the safe pipeline, independently verify books, and export Week 3 evidence."""
    started = time.perf_counter()
    pipeline = run_pipeline(spec_path, roles_path, ownership_path, output_dir, base_url)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    timing = {
        "status": "MEASURED",
        "elapsed_ms": elapsed_ms,
        "case_count": len(pipeline["raw_results"]),
        "configured_inter_case_delay_ms": 150,
        "execution_mode": "Read-only pipeline; preflight included; all cases use known local fixtures.",
    }
    verification = independently_verify_books(pipeline["roles_config"], pipeline["fixtures"], base_url)
    findings = classify_findings(verification, pipeline["endpoints"])
    zap_status_path = output_dir / "zap" / "zap_run_status.json"
    zap_status = read_json(zap_status_path) if zap_status_path.exists() else {
        "status": "PENDING_CONFIGURATION",
        "finding_count": None,
        "note": "ZAP execution has not yet completed; do not infer detections or false negatives from this placeholder.",
    }
    comparison = build_comparison(timing, verification, zap_status)

    write_redacted_json(output_dir / "week3_script_timing.json", timing)
    write_redacted_json(output_dir / "week3_manual_verification.json", verification)
    write_redacted_json(output_dir / "week3_findings.json", findings)
    write_redacted_json(output_dir / "week3_comparison.json", comparison)
    return {**pipeline, "timing": timing, "verification": verification, "findings": findings, "comparison": comparison}
