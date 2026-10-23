"""Compatibility wrapper for the packaged local VAmPI CLI."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vampi_authz_lab.cli import main as packaged_main


def main() -> int:
    """Run the packaged `run` subcommand for existing Week 2 workflows."""
    return packaged_main(["run", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
