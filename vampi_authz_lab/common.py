"""Shared, credential-safe file export helpers for the local-lab package."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TOKEN_PATTERN = re.compile(r"(?:Bearer\s+|eyJ)[A-Za-z0-9._-]{12,}")


def read_json(path: str | Path) -> Any:
    """Load JSON with an actionable error if the file cannot be decoded."""
    source = Path(path)
    try:
        with source.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise ValueError(f"Required file does not exist: {source}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {source}: {error.msg}.") from error


def write_redacted_json(path: str | Path, value: Any) -> None:
    """Write JSON only when it contains no bearer token or JWT-like value."""
    destination = Path(path)
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    if TOKEN_PATTERN.search(serialized):
        raise RuntimeError(f"Refusing to write token-like data to {destination.name}.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialized + "\n", encoding="utf-8")
