"""Validated timing-evidence discovery for the final comparison artifact."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from authz_lab.common import read_json


@dataclass(frozen=True)
class TimingEvidence:
    """A validated automated-timing observation or an explicit absence reason."""

    status: str
    source: Path | None
    elapsed_ms: float | None
    case_count: int | None
    reason: str | None = None


LEGACY_TIMING_FILENAMES = (
    Path("rerun-week3") / "week3_script_timing.json",
    Path("week3_script_timing.json"),
)
CURRENT_TIMING_FILENAME = Path("rerun-verification") / "read_only_verification_timing.json"


def _validate_timing_payload(payload: Any, source: Path) -> TimingEvidence:
    if not isinstance(payload, dict):
        return TimingEvidence("INVALID", source, None, None, "Timing evidence must be a JSON object.")
    if payload.get("status") != "MEASURED":
        return TimingEvidence("INVALID", source, None, None, "Timing evidence status must be MEASURED.")

    elapsed_ms = payload.get("elapsed_ms")
    if (
        isinstance(elapsed_ms, bool)
        or not isinstance(elapsed_ms, (int, float))
        or not math.isfinite(elapsed_ms)
        or elapsed_ms < 0
    ):
        return TimingEvidence(
            "INVALID", source, None, None, "Timing evidence elapsed_ms must be a finite non-negative number."
        )

    case_count = payload.get("case_count")
    if isinstance(case_count, bool) or not isinstance(case_count, int) or case_count <= 0:
        return TimingEvidence(
            "INVALID", source, None, None, "Timing evidence case_count must be a positive integer."
        )

    return TimingEvidence("AVAILABLE", source, float(elapsed_ms), case_count)


def load_timing_evidence(
    *,
    results_root: str | Path,
    timing_file: str | Path | None = None,
) -> TimingEvidence:
    """Load explicit, current, or retained legacy timing evidence safely.

    An explicit path is authoritative. Without one, the current semantic path is
    preferred and the retained legacy paths are considered only when it is absent.
    Missing or malformed evidence is represented in the result rather than coerced
    to an elapsed value.
    """
    root = Path(results_root)
    candidates = (
        (Path(timing_file),)
        if timing_file is not None
        else (root / CURRENT_TIMING_FILENAME, *(root / path for path in LEGACY_TIMING_FILENAMES))
    )
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        if timing_file is not None:
            return TimingEvidence("UNAVAILABLE", Path(timing_file), None, None, "Explicit timing evidence file was not found.")
        return TimingEvidence(
            "UNAVAILABLE", None, None, None, "No current or retained automated timing evidence file was found."
        )

    try:
        payload = read_json(source)
    except ValueError as error:
        return TimingEvidence("INVALID", source, None, None, f"Timing evidence could not be read: {error}")
    return _validate_timing_payload(payload, source)
