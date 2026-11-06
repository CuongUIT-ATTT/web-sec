"""CLI regression coverage for packaged resources and timing evidence."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authz_lab.evaluation import cli


VALID_TIMING = {
    "status": "MEASURED",
    "elapsed_ms": 2032.298,
    "case_count": 12,
}


class EvaluationCliTests(unittest.TestCase):
    def write_json(self, path: Path, payload: object) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def run_cli(self, arguments: list[str], *, cwd: Path | None = None):
        captured_timing = []
        captured_allowlists = []
        result = {"overall_verdict": "DENIED_CONTROL", "cases": []}

        def build_comparison(**kwargs):
            captured_timing.append(kwargs["timing_evidence"])
            return {
                "bfla_disposable": {"status": "EXECUTED", "verdict": "DENIED_CONTROL"},
                "owasp_zap": {"status": "NOT_RUN"},
                "manual_postman_or_burp": {"status": "PENDING_HUMAN_MEASUREMENT"},
                "custom_script": {"status": kwargs["timing_evidence"].status},
            }

        def bootstrap(**kwargs):
            captured_allowlists.append(Path(kwargs["allowlist_path"]))
            return {"status": "BOOTSTRAP_NOT_READY"}

        old_cwd = Path.cwd()
        stdout = io.StringIO()
        try:
            if cwd is not None:
                os.chdir(cwd)
            with patch("authz_lab.evaluation.cli.run_bfla_evaluation", return_value=result), patch(
                "authz_lab.evaluation.cli.build_final_comparison", side_effect=build_comparison
            ), patch("authz_lab.evaluation.cli.write_comparison", return_value=Path("comparison.json")), patch(
                "authz_lab.zap.runner.run_zap_authentication_bootstrap", side_effect=bootstrap
            ), contextlib.redirect_stdout(stdout):
                status = cli.main(arguments)
        finally:
            os.chdir(old_cwd)
        return status, captured_timing, captured_allowlists, stdout.getvalue()

    def test_packaged_default_allowlist_resolves_outside_repository(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status, _timing, allowlists, _stdout = self.run_cli(
                ["--run-id", "abcdefgh", "--zap-bootstrap-only", "--zap-context-mode", "preloaded-desktop"],
                cwd=Path(tmpdir),
            )
        self.assertEqual(status, 0)
        self.assertEqual(len(allowlists), 1)
        self.assertTrue(allowlists[0].is_file())
        self.assertEqual(allowlists[0].name, "allowlist-v2.json")
        self.assertNotIn(str(tmpdir), str(allowlists[0]))

    def test_explicit_allowlist_path_overrides_packaged_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            allowlist = self.write_json(root / "reviewed.json", {"marker": "explicit"})
            status, _timing, allowlists, _stdout = self.run_cli(
                [
                    "--run-id", "abcdefgh", "--zap-bootstrap-only", "--zap-context-mode", "preloaded-desktop",
                    "--allowlist", str(allowlist),
                ],
            )
        self.assertEqual(status, 0)
        self.assertEqual(allowlists, [allowlist])

    def test_explicit_timing_file_is_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            timing = self.write_json(root / "chosen.json", VALID_TIMING)
            status, timings, _allowlists, _stdout = self.run_cli(
                ["--run-id", "abcdefgh", "--skip-zap", "--results-root", str(root), "--timing-file", str(timing)],
            )
        self.assertEqual(status, 0)
        self.assertEqual(timings[0].status, "AVAILABLE")
        self.assertEqual(timings[0].elapsed_ms, 2032.298)

    def test_default_and_legacy_timing_discovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_json(root / "rerun-verification" / "read_only_verification_timing.json", VALID_TIMING)
            status, timings, _allowlists, _stdout = self.run_cli(
                ["--run-id", "abcdefgh", "--skip-zap", "--results-root", str(root)],
            )
            self.assertEqual(status, 0)
            self.assertEqual(timings[0].status, "AVAILABLE")

            (root / "rerun-verification" / "read_only_verification_timing.json").unlink()
            self.write_json(root / "rerun-week3" / "week3_script_timing.json", VALID_TIMING)
            status, timings, _allowlists, _stdout = self.run_cli(
                ["--run-id", "abcdefgh", "--skip-zap", "--results-root", str(root)],
            )
        self.assertEqual(status, 0)
        self.assertEqual(timings[0].status, "AVAILABLE")
        self.assertTrue(str(timings[0].source).endswith("rerun-week3/week3_script_timing.json"))

    def test_missing_and_malformed_timing_are_honest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            status, timings, _allowlists, _stdout = self.run_cli(
                ["--run-id", "abcdefgh", "--skip-zap", "--results-root", str(root)],
            )
            self.assertEqual(status, 0)
            self.assertEqual(timings[0].status, "UNAVAILABLE")
            self.assertIsNone(timings[0].elapsed_ms)

            malformed = root / "bad.json"
            malformed.write_text("{bad-json", encoding="utf-8")
            status, timings, _allowlists, _stdout = self.run_cli(
                ["--run-id", "abcdefgh", "--skip-zap", "--results-root", str(root), "--timing-file", str(malformed)],
            )
        self.assertEqual(status, 0)
        self.assertEqual(timings[0].status, "INVALID")
        self.assertIsNone(timings[0].elapsed_ms)


if __name__ == "__main__":
    unittest.main()
