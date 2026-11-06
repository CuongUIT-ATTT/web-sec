"""Regression coverage for automated timing evidence discovery."""

import json
import math
import tempfile
import unittest
from pathlib import Path

from authz_lab.evaluation.timing import (
    CURRENT_TIMING_FILENAME,
    LEGACY_TIMING_FILENAMES,
    load_timing_evidence,
)


VALID_TIMING = {
    "status": "MEASURED",
    "elapsed_ms": 2032.298,
    "case_count": 12,
    "configured_inter_case_delay_ms": 150,
}


class TimingEvidenceTests(unittest.TestCase):
    def write_json(self, path: Path, payload: object) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_explicit_timing_file_has_priority(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_json(root / CURRENT_TIMING_FILENAME, {**VALID_TIMING, "elapsed_ms": 1})
            explicit = self.write_json(root / "chosen.json", VALID_TIMING)
            timing = load_timing_evidence(results_root=root, timing_file=explicit)
        self.assertEqual(timing.status, "AVAILABLE")
        self.assertEqual(timing.source, explicit)
        self.assertEqual(timing.elapsed_ms, 2032.298)

    def test_uses_current_default_timing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current = self.write_json(root / CURRENT_TIMING_FILENAME, VALID_TIMING)
            timing = load_timing_evidence(results_root=root)
        self.assertEqual(timing.status, "AVAILABLE")
        self.assertEqual(timing.source, current)

    def test_uses_retained_legacy_timing_file_when_current_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy = self.write_json(root / LEGACY_TIMING_FILENAMES[0], VALID_TIMING)
            timing = load_timing_evidence(results_root=root)
        self.assertEqual(timing.status, "AVAILABLE")
        self.assertEqual(timing.source, legacy)

    def test_uses_flat_retained_legacy_timing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy = self.write_json(root / LEGACY_TIMING_FILENAMES[1], VALID_TIMING)
            timing = load_timing_evidence(results_root=root)
        self.assertEqual(timing.status, "AVAILABLE")
        self.assertEqual(timing.source, legacy)

    def test_missing_timing_file_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            timing = load_timing_evidence(results_root=tmpdir)
        self.assertEqual(timing.status, "UNAVAILABLE")
        self.assertIsNone(timing.elapsed_ms)
        self.assertIn("No current or retained", timing.reason)

    def test_missing_explicit_timing_file_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_json(root / CURRENT_TIMING_FILENAME, VALID_TIMING)
            timing = load_timing_evidence(results_root=root, timing_file=root / "missing.json")
        self.assertEqual(timing.status, "UNAVAILABLE")
        self.assertIsNone(timing.elapsed_ms)

    def test_malformed_timing_file_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            malformed = Path(tmpdir) / "bad.json"
            malformed.write_text("{not-json", encoding="utf-8")
            timing = load_timing_evidence(results_root=tmpdir, timing_file=malformed)
        self.assertEqual(timing.status, "INVALID")
        self.assertIsNone(timing.elapsed_ms)

    def test_invalid_timing_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid = self.write_json(
                Path(tmpdir) / "invalid.json",
                {"status": "MEASURED", "elapsed_ms": math.inf, "case_count": "12"},
            )
            timing = load_timing_evidence(results_root=tmpdir, timing_file=invalid)
        self.assertEqual(timing.status, "INVALID")
        self.assertIsNone(timing.elapsed_ms)


if __name__ == "__main__":
    unittest.main()
