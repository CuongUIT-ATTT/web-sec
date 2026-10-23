"""Console interface for the safe local VAmPI authorization lab tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from week2.request_runner import ALLOWED_BASE_URL, validate_base_url

from .pipeline import run_pipeline, run_verification, run_week3_workflow, validate_inputs
from .zap_allowlist import approved_request_pairs, load_zap_allowlist

# Default artifacts belong to the working project directory, not site-packages.
PROJECT_ROOT = Path.cwd().resolve()


def add_input_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the shared explicit local-lab artifact arguments to a subcommand."""
    parser.add_argument("--spec", type=Path, default=PROJECT_ROOT / "vampi_spec.json", help="OpenAPI JSON document.")
    parser.add_argument("--roles-config", type=Path, default=PROJECT_ROOT / "roles_config.json", help="Local role-token JSON file.")
    parser.add_argument("--ownership", type=Path, default=PROJECT_ROOT / "ownership.csv", help="Fixture ownership CSV file.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "results", help="Directory for redacted JSON artifacts.")
    parser.add_argument("--base-url", default=ALLOWED_BASE_URL, help=f"Must be exactly {ALLOWED_BASE_URL}.")


def build_parser() -> argparse.ArgumentParser:
    """Build the stable command-line interface without allowing arbitrary targets."""
    parser = argparse.ArgumentParser(
        prog="vampi-authz-lab",
        description="Safe, fixture-backed BOLA/BFLA teaching-lab checks for local VAmPI only.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("check-inputs", "Validate spec, role configuration, and ownership CSV without network access."),
        ("run", "Execute the safe read-only authorization pipeline."),
        ("verify", "Run independent known-book verification and classification."),
        ("week3", "Run timed pipeline plus independent Week 3 verification."),
    ):
        subcommand = subcommands.add_parser(command, help=help_text)
        add_input_arguments(subcommand)

    zap_manifest = subcommands.add_parser(
        "check-zap-allowlist",
        help="Validate the reviewed GET-only local ZAP manifest; this does not start ZAP or send requests.",
    )
    zap_manifest.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "zap" / "allowlist-v1.json",
        help="Reviewed local ZAP allowlist JSON document.",
    )
    return parser


def _render_counts(results: list[dict[str, object]]) -> str:
    counts: dict[str, int] = {}
    for result in results:
        verdict = str(result["verdict"])
        counts[verdict] = counts.get(verdict, 0) + 1
    return ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    """Dispatch one safe subcommand and return shell-compatible status codes."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check-zap-allowlist":
            manifest = load_zap_allowlist(args.manifest)
            approved = approved_request_pairs(manifest)
            print(
                f"ZAP allowlist valid: {manifest['assessment_id']} permits {len(approved)} "
                f"GET request(s) at {manifest['target']}; no scan was started."
            )
            return 0

        validate_base_url(args.base_url)
        if args.command == "check-inputs":
            report = validate_inputs(args.spec, args.roles_config, args.ownership)
            print(
                f"Inputs valid: {report['operation_count']} operations, {report['fixture_count']} fixtures, "
                f"roles={','.join(report['role_names'])}; ownership input is CSV."
            )
            return 0
        if args.command == "run":
            pipeline = run_pipeline(args.spec, args.roles_config, args.ownership, args.output_dir, args.base_url)
            print(f"Completed {len(pipeline['final_results'])} read-only cases: {_render_counts(pipeline['final_results'])}")
            print(f"Reports written to {args.output_dir}")
            return 0
        if args.command == "verify":
            verification = run_verification(args.spec, args.roles_config, args.ownership, args.output_dir, args.base_url)
            confirmed = sum(item["outcome"] == "CONFIRMED_USER_TO_USER_BOLA" for item in verification["verification"])
            print(f"Independent verification completed: {confirmed} user-to-user BOLA cases reproduced.")
            print(f"Reports written to {args.output_dir}")
            return 0

        workflow = run_week3_workflow(args.spec, args.roles_config, args.ownership, args.output_dir, args.base_url)
        print(
            f"Week 3 workflow completed: {workflow['timing']['case_count']} cases in "
            f"{workflow['timing']['elapsed_ms']} ms."
        )
        print(f"Reports written to {args.output_dir}")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Command stopped safely: {error}", file=sys.stderr)
        return 2
