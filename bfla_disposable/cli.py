"""Opt-in CLI for a manifest-bound, disposable local BFLA experiment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manifest import BflaManifestError, expected_project_name, validate_run_directory, validate_run_id, write_manifest
from .preflight import preflight
from .runner import BflaExecutionError, execute, prepare
from .teardown import teardown

PROJECT_ROOT = Path.cwd().resolve()
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "results" / "bfla-disposable"
DEFAULT_RUNS_ROOT = PROJECT_ROOT / ".bfla-runs"
DEFAULT_COMPOSE_FILE = PROJECT_ROOT / "bfla-disposable" / "compose.yaml"


def _add_run_arguments(parser: argparse.ArgumentParser, *, include_compose: bool = False) -> None:
    parser.add_argument("--run-id", required=True, help="Validated lowercase disposable run identifier.")
    parser.add_argument("--project", help="Must equal vampi-bfla-<run-id>.")
    parser.add_argument("--run-dir", type=Path, help="Must end with <run-id> beneath .bfla-runs.")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT, help="Credential-free BFLA evidence directory.")
    if include_compose:
        parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE, help="Fixed disposable Compose definition.")


def _resolved_run_paths(args: argparse.Namespace) -> tuple[str, Path]:
    run_id = validate_run_id(args.run_id)
    project = args.project or expected_project_name(run_id)
    run_dir = validate_run_directory(args.run_dir or DEFAULT_RUNS_ROOT / run_id, run_id)
    if run_dir.resolve().parent != DEFAULT_RUNS_ROOT.resolve():
        raise BflaManifestError("Disposable run directory must be directly below the project .bfla-runs directory.")
    return project, run_dir


def build_parser() -> argparse.ArgumentParser:
    """Build a non-generic CLI with no target, method, or path override flags."""
    parser = argparse.ArgumentParser(
        prog="vampi-bfla-disposable",
        description="Explicitly scoped destructive authorization control for a disposable local VAmPI lab only.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser("create-manifest", help="Write only a non-secret fixed-scope manifest.")
    _add_run_arguments(create)
    preflight_parser = subcommands.add_parser(
        "preflight",
        help="Attest shared-lab invariance and an empty disposable destination before Compose starts.",
    )
    _add_run_arguments(preflight_parser)
    prepare_parser = subcommands.add_parser("prepare", help="Create disposable fixtures after Compose is already running.")
    _add_run_arguments(prepare_parser)
    execute_parser = subcommands.add_parser("execute", help="Run only the two declared delete controls.")
    _add_run_arguments(execute_parser)
    teardown_parser = subcommands.add_parser("teardown", help="Destroy only the matching disposable Compose project and volume.")
    _add_run_arguments(teardown_parser, include_compose=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch an explicit stage and preserve nonzero status for confirmed BFLA."""
    args = build_parser().parse_args(argv)
    try:
        project, run_dir = _resolved_run_paths(args)
        if args.command == "create-manifest":
            path = write_manifest(args.run_id, args.results_root)
            print(f"Created credential-free disposable BFLA manifest at {path}.")
            return 0
        if args.command == "preflight":
            receipt = preflight(args.run_id, project, run_dir, args.results_root)
            print(f"Disposable BFLA preflight completed: {receipt['status']}.")
            return 0
        if args.command == "prepare":
            path = prepare(args.run_id, project, run_dir, args.results_root)
            print(f"Prepared only the manifest-bound disposable BFLA fixtures from {path}.")
            return 0
        if args.command == "execute":
            result = execute(args.run_id, project, run_dir, args.results_root)
            print(f"Disposable BFLA execution completed with outcome {result['outcome']}.")
            return 10 if result["outcome"] == "BFLA_CONFIRMED_DESTRUCTIVE" else 0 if result["outcome"] == "DENIED_CONTROL" else 2
        receipt = teardown(args.run_id, project, run_dir, args.compose_file, args.results_root)
        print(f"Disposable teardown completed: {receipt['status']}.")
        return 0
    except (BflaManifestError, BflaExecutionError, OSError, ValueError, RuntimeError) as error:
        print(f"Command stopped safely: {error}", file=sys.stderr)
        return 2
