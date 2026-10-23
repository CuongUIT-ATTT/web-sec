"""Week 4 orchestration entry point.

Usage::

    python3 -I week4/run_week4.py --run-id <id>

This script coordinates the Week 4 deliverables:
1. BFLA findings from an already-completed disposable run
2. ZAP Access Control scan (if ZAP daemon is available)
3. Three-method comparison artifact

The disposable BFLA workflow (create-manifest → preflight → compose up →
prepare → execute → teardown) must be run separately via the
``vampi-bfla-disposable`` CLI before calling this script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from week4.bfla_executor import BflaGuardrailError, run_bfla_week4
from week4.comparison_builder import build_week4_comparison, write_comparison


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Week 4 orchestration: BFLA findings, ZAP scan, and final comparison.",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="BFLA disposable run ID (must already have execution evidence).",
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Root directory for Week 4 output artifacts.",
    )
    parser.add_argument(
        "--bfla-results-root",
        default="results/bfla-disposable",
        help="Root directory for BFLA disposable evidence.",
    )
    parser.add_argument(
        "--skip-zap",
        action="store_true",
        help="Skip the ZAP scan (use when ZAP is not running).",
    )
    parser.add_argument(
        "--zap-api-key",
        default="",
        help="ZAP API key (empty for development mode).",
    )
    parser.add_argument(
        "--allowlist",
        default="zap/allowlist-v2.json",
        help="ZAP allowlist manifest path.",
    )
    parser.add_argument(
        "--zap-context",
        help="Local private reviewed .context file (required unless --skip-zap).",
    )
    parser.add_argument(
        "--zap-context-in-container",
        help="Absolute path of that Context as mounted inside the ZAP container.",
    )
    parser.add_argument(
        "--zap-attestation",
        default="zap/imported-context-attestation.json",
        help="Non-secret review attestation for the imported Context.",
    )
    parser.add_argument(
        "--zap-html-on-host",
        help="Disposable host path for the mounted temporary ZAP HTML report.",
    )
    parser.add_argument(
        "--zap-html-in-container",
        help="Absolute mounted temporary HTML-report path inside the ZAP container.",
    )

    args = parser.parse_args(argv)

    # ── Phase 1: BFLA findings ──
    print(f"[Week 4] Building BFLA findings from run {args.run_id}...")
    try:
        bfla_findings = run_bfla_week4(
            args.run_id,
            results_root=args.results_root,
            bfla_results_root=args.bfla_results_root,
        )
        print(f"  BFLA verdict: {bfla_findings['overall_verdict']}")
    except (BflaGuardrailError, OSError, ValueError) as error:
        print(f"  BFLA error: {error}", file=sys.stderr)
        bfla_findings = None

    # ── Phase 2: ZAP scan ──
    zap_report = None
    if args.skip_zap:
        print("[Week 4] ZAP scan skipped (--skip-zap).")
    else:
        print("[Week 4] Running ZAP Access Control scan...")
        try:
            from week4.zap_runner import run_zap_access_control

            zap_report = run_zap_access_control(
                api_key=args.zap_api_key,
                allowlist_path=args.allowlist,
                context_path=args.zap_context,
                zap_context_path=args.zap_context_in_container,
                context_attestation_path=args.zap_attestation,
                host_report_path=args.zap_html_on_host,
                zap_report_path=args.zap_html_in_container,
                report_path=Path(args.results_root) / "zap" / "zap_access_control_report.json",
                status_path=Path(args.results_root) / "zap" / "zap_run_status.json",
            )
            print(f"  ZAP status: {zap_report.get('status', 'UNKNOWN')}")
        except Exception as error:
            print(f"  ZAP error: {error}", file=sys.stderr)
            zap_report = None

    # ── Phase 3: Comparison ──
    print("[Week 4] Building final comparison...")
    worksheet_path = Path(args.results_root) / "week3_manual_worksheet.md"
    timing_path = Path(args.results_root) / "rerun-week3" / "week3_script_timing.json"

    comparison = build_week4_comparison(
        bfla_findings=bfla_findings,
        zap_report=zap_report,
        manual_worksheet_path=str(worksheet_path),
        script_timing_path=str(timing_path) if timing_path.is_file() else None,
    )
    output = write_comparison(
        comparison,
        Path(args.results_root) / "week4_comparison_final.json",
    )
    print(f"  Comparison written to {output}")

    # ── Summary ──
    print("\n[Week 4] Summary:")
    print(f"  BFLA:   {comparison['bfla_disposable']['status']} "
          f"({comparison['bfla_disposable'].get('verdict', 'N/A')})")
    print(f"  ZAP:    {comparison['owasp_zap']['status']}")
    print(f"  Manual: {comparison['manual_postman_or_burp']['status']}")
    print(f"  Script: {comparison['custom_script']['status']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
