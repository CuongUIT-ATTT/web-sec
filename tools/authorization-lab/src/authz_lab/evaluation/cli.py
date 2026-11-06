"""Authorization-evaluation orchestration entry point.

Usage::

    vampi-authz-evaluate --run-id <id>

This command coordinates the final evaluation deliverables:
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
from contextlib import nullcontext
from importlib import resources
from pathlib import Path
from typing import ContextManager

from .bfla_evidence import BflaGuardrailError, run_bfla_evaluation
from .comparison import build_final_comparison, write_comparison
from .timing import load_timing_evidence


def _allowlist_path_context(allowlist: Path | None) -> ContextManager[Path]:
    """Yield an explicit allowlist or the reviewed packaged v2 manifest."""
    if allowlist is not None:
        return nullcontext(allowlist)
    resource = resources.files("authz_lab").joinpath("fixtures", "zap", "allowlist-v2.json")
    return resources.as_file(resource)


DEFAULT_ALLOWLIST_HELP = "Reviewed packaged ZAP allowlist manifest path."


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
        "--zap-bootstrap-only",
        action="store_true",
        help="Read-only Desktop readiness check before the operator authenticates and quiesces traffic; never seeds or scans.",
    )
    parser.add_argument(
        "--zap-api-key",
        default="",
        help="ZAP API key (empty for development mode).",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        help=DEFAULT_ALLOWLIST_HELP,
    )
    parser.add_argument(
        "--timing-file",
        type=Path,
        help="Validated automated timing evidence JSON; overrides default and retained locations.",
    )
    parser.add_argument(
        "--zap-context-mode",
        choices=("import", "preloaded-desktop"),
        default="import",
        help="Context source: Docker import (default) or an already-loaded local ZAP Desktop Context.",
    )
    parser.add_argument(
        "--zap-context",
        help="Local private reviewed .context file used for fingerprint attestation (required unless --skip-zap).",
    )
    parser.add_argument(
        "--zap-context-in-container",
        help="Absolute Context path visible to ZAP; required only with --zap-context-mode import.",
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
        help="Absolute temporary HTML-report path visible to the ZAP process.",
    )

    args = parser.parse_args(argv)
    if args.skip_zap and args.zap_bootstrap_only:
        parser.error("--skip-zap cannot be combined with --zap-bootstrap-only")
    if args.zap_bootstrap_only and args.zap_context_mode != "preloaded-desktop":
        parser.error("--zap-bootstrap-only requires --zap-context-mode preloaded-desktop")

    # ── Phase 1: BFLA findings ──
    print(f"[Evaluation] Building BFLA findings from run {args.run_id}...")
    try:
        bfla_findings = run_bfla_evaluation(
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
        print("[Evaluation] ZAP scan skipped (--skip-zap).")
    elif args.zap_bootstrap_only:
        print("[Evaluation] Verifying ZAP Desktop authentication bootstrap...")
        try:
            from ..zap.runner import run_zap_authentication_bootstrap

            with _allowlist_path_context(args.allowlist) as allowlist_path:
                zap_report = run_zap_authentication_bootstrap(
                    api_key=args.zap_api_key,
                    context_mode=args.zap_context_mode,
                    allowlist_path=allowlist_path,
                    context_path=args.zap_context,
                    context_attestation_path=args.zap_attestation,
                    bootstrap_path=Path(args.results_root) / "zap" / "zap_bootstrap_readiness.json",
                )
            print(f"  ZAP bootstrap: {zap_report.get('status', 'UNKNOWN')}")
        except Exception as error:
            print(f"  ZAP bootstrap error: {error}", file=sys.stderr)
            zap_report = None
    else:
        print("[Evaluation] Running ZAP Access Control scan...")
        try:
            from ..zap.runner import run_zap_access_control

            with _allowlist_path_context(args.allowlist) as allowlist_path:
                zap_report = run_zap_access_control(
                    api_key=args.zap_api_key,
                    context_mode=args.zap_context_mode,
                    allowlist_path=allowlist_path,
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
    print("[Evaluation] Building final comparison...")
    worksheet_path = Path(args.results_root) / "manual_verification_worksheet.md"
    timing_evidence = load_timing_evidence(
        results_root=args.results_root,
        timing_file=args.timing_file,
    )

    comparison = build_final_comparison(
        bfla_findings=bfla_findings,
        zap_report=zap_report,
        manual_worksheet_path=str(worksheet_path),
        timing_evidence=timing_evidence,
    )
    output = write_comparison(
        comparison,
        Path(args.results_root) / "authorization_comparison_final.json",
    )
    print(f"  Comparison written to {output}")

    # ── Summary ──
    print("\n[Evaluation] Summary:")
    print(f"  BFLA:   {comparison['bfla_disposable']['status']} "
          f"({comparison['bfla_disposable'].get('verdict', 'N/A')})")
    print(f"  ZAP:    {comparison['owasp_zap']['status']}")
    print(f"  Manual: {comparison['manual_postman_or_burp']['status']}")
    print(f"  Script: {comparison['custom_script']['status']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
