"""Tests for week4.comparison_builder — three-method comparison artifact."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from week4.comparison_builder import (
    _parse_manual_worksheet,
    build_week4_comparison,
    write_comparison,
)


class ParseManualWorksheetTests(unittest.TestCase):
    """Worksheet parser must never auto-fill observation data."""

    def test_returns_pending_when_file_missing(self):
        result = _parse_manual_worksheet("/nonexistent/path.md")
        self.assertEqual(result["status"], "PENDING_HUMAN_MEASUREMENT")
        self.assertIsNone(result["elapsed_minutes"])
        self.assertIsNone(result["confirmed_findings"])

    def test_returns_pending_when_columns_unfilled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "worksheet.md"
            path.write_text(
                "| Mẫu | Endpoint | Auth | Expected | Status | Findings | Time |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| M-01 | GET /books/v1/x | userA | 200 |  |  |  |\n"
                "| M-02 | GET /books/v1/y | userB | 200 |  |  |  |\n",
                encoding="utf-8",
            )
            result = _parse_manual_worksheet(str(path))
        self.assertEqual(result["status"], "PENDING_HUMAN_MEASUREMENT")

    def test_completed_observations_without_timing_are_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "worksheet.md"
            rows = [
                "| M-01 | GET /a | userA | 200 | 200 | Owner control | — |",
                "| M-02 | GET /a | userB | deny | 200 | **BOLA confirmed** | — |",
                "| M-03 | GET /b | userA | deny | 200 | **BOLA confirmed** | — |",
                "| M-04 | GET /a | none | 401 | 401 | Denied | — |",
                "| M-05 | GET /a | invalid | 401 | 401 | Denied | — |",
                "| M-06 | GET /u | none | 200 | 200 | Public observation | — |",
                "| M-07 | GET /me | userA | 200 | 200 | Identity control | — |",
            ]
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            result = _parse_manual_worksheet(path)
        self.assertEqual(result["status"], "COMPLETED_NO_TIMING")
        self.assertEqual(result["filled_case_count"], 7)
        self.assertEqual(result["confirmed_findings"], 2)
        self.assertIsNone(result["elapsed_minutes"])


class BuildWeek4ComparisonTests(unittest.TestCase):
    """Comparison builder must preserve honest statuses."""

    def test_preserves_pending_manual_and_not_run_zap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            comparison = build_week4_comparison(
                bfla_findings=None,
                zap_report=None,
                manual_worksheet_path=Path(tmpdir) / "missing.md",
            )
        self.assertEqual(
            comparison["manual_postman_or_burp"]["status"],
            "PENDING_HUMAN_MEASUREMENT",
        )
        self.assertEqual(comparison["owasp_zap"]["status"], "NOT_RUN")
        self.assertEqual(comparison["bfla_disposable"]["status"], "NOT_RUN")
        self.assertEqual(comparison["custom_script"]["status"], "MEASURED")

    def test_incorporates_bfla_denied_control(self):
        bfla = {
            "overall_verdict": "DENIED_CONTROL",
            "finding_id": "W4-BFLA-01",
            "endpoint": "DELETE /users/v1/{username}",
            "cases": [
                {"id": "non-admin-delete-victim", "verdict": "DENIED"},
                {"id": "admin-delete-control", "verdict": "POSITIVE_CONTROL"},
            ],
        }
        comparison = build_week4_comparison(
            bfla_findings=bfla,
            zap_report=None,
        )
        self.assertEqual(comparison["bfla_disposable"]["status"], "EXECUTED")
        self.assertEqual(
            comparison["bfla_disposable"]["verdict"], "DENIED_CONTROL"
        )
        self.assertEqual(comparison["bfla_disposable"]["case_count"], 2)

    def test_incorporates_zap_not_run_with_reason(self):
        zap = {
            "status": "NOT_RUN",
            "reason": "Site tree containment failed.",
        }
        comparison = build_week4_comparison(
            bfla_findings=None,
            zap_report=zap,
        )
        self.assertEqual(comparison["owasp_zap"]["status"], "NOT_RUN")
        self.assertIn("containment", comparison["owasp_zap"]["reason"])

    def test_bootstrap_requires_authentication_and_quiescence(self):
        comparison = build_week4_comparison(
            bfla_findings=None,
            zap_report={"status": "BOOTSTRAP_REQUIRES_OPERATOR_AUTH_AND_QUIESCE"},
        )
        zap = comparison["owasp_zap"]
        self.assertEqual(zap["status"], "NOT_RUN")
        self.assertIn("authentication and traffic quiescence", zap["reason"])

    def test_incorporates_zap_completed(self):
        zap = {
            "status": "COMPLETED",
            "scan_result_count": 10,
            "unauthorized_access_findings": [
                {"url": "http://127.0.0.1:5000/books/v1/a", "user": "userB",
                 "access_result": "ILLEGAL"},
            ],
            "comparison_with_known_bola": {
                "known_bola_count": 2,
                "zap_detected_known_bola_paths": ["/books/v1/a"],
            },
        }
        comparison = build_week4_comparison(
            bfla_findings=None,
            zap_report=zap,
        )
        self.assertEqual(comparison["owasp_zap"]["status"], "COMPLETED")
        self.assertEqual(comparison["owasp_zap"]["finding_count"], 10)
        self.assertEqual(comparison["owasp_zap"]["unauthorized_access_count"], 1)


class WriteComparisonTests(unittest.TestCase):
    """Written comparison must pass redaction checks."""

    def test_writes_valid_json(self):
        comparison = build_week4_comparison(
            bfla_findings=None,
            zap_report=None,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_comparison(comparison, Path(tmpdir) / "out.json")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["custom_script"]["status"], "MEASURED")
        self.assertFalse(
            any("Bearer" in str(v) or "eyJ" in str(v)
                for v in json.dumps(loaded).split())
        )


if __name__ == "__main__":
    unittest.main()
