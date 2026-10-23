"""Compatibility wrapper for the packaged local VAmPI Week 3 workflow."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vampi_authz_lab.cli import main as packaged_main


def main() -> int:
    """Run the packaged `week3` subcommand for existing Week 3 workflows."""
    return packaged_main(["week3", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
