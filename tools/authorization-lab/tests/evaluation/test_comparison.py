"""Tests for authz_lab.evaluation.comparison — three-method comparison artifact."""

import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from authz_lab.evaluation.comparison import (
    _parse_manual_worksheet,
    build_final_comparison,
    write_comparison,
)
from authz_lab.evaluation.timing import TimingEvidence


class OfflineTests(unittest.TestCase):
    def setUp(self):
        blocker = patch("socket.socket.connect", side_effect=AssertionError("network blocked"))
        blocker.start()
        self.addCleanup(blocker.stop)


class ParseManualWorksheetTests(OfflineTests):
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


class BuildWeek4ComparisonTests(OfflineTests):
    """Comparison builder must preserve honest statuses."""

    def test_preserves_pending_manual_and_not_run_zap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            comparison = build_final_comparison(
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
        self.assertEqual(comparison["custom_script"]["status"], "TIMING_NOT_AVAILABLE")
        self.assertIsNone(comparison["custom_script"]["elapsed_ms"])

    def test_incorporates_validated_script_timing(self):
        timing = TimingEvidence("AVAILABLE", Path("results/timing.json"), 2032.298, 12)
        comparison = build_final_comparison(
            bfla_findings=None,
            zap_report=None,
            timing_evidence=timing,
        )
        script = comparison["custom_script"]
        self.assertEqual(script["status"], "MEASURED")
        self.assertEqual(script["elapsed_ms"], 2032.298)
        self.assertEqual(script["case_count"], 12)
        self.assertEqual(script["timing_source"], "results/timing.json")

    def test_preserves_invalid_timing_reason(self):
        timing = TimingEvidence("INVALID", Path("results/bad.json"), None, None, "Timing evidence status must be MEASURED.")
        comparison = build_final_comparison(
            bfla_findings=None,
            zap_report=None,
            timing_evidence=timing,
        )
        script = comparison["custom_script"]
        self.assertEqual(script["status"], "TIMING_NOT_AVAILABLE")
        self.assertEqual(script["timing_status"], "INVALID")
        self.assertIsNone(script["elapsed_ms"])

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
        comparison = build_final_comparison(
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
        comparison = build_final_comparison(
            bfla_findings=None,
            zap_report=zap,
        )
        self.assertEqual(comparison["owasp_zap"]["status"], "NOT_RUN")
        self.assertIn("containment", comparison["owasp_zap"]["reason"])

    def test_bootstrap_requires_authentication_and_quiescence(self):
        comparison = build_final_comparison(
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
        comparison = build_final_comparison(
            bfla_findings=None,
            zap_report=zap,
        )
        self.assertEqual(comparison["owasp_zap"]["status"], "COMPLETED")
        self.assertEqual(comparison["owasp_zap"]["finding_count"], 10)
        self.assertEqual(comparison["owasp_zap"]["unauthorized_access_count"], 1)

    def test_dynamically_reads_case_and_bola_counts_from_rerun_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            timing_file = root / "week3_script_timing.json"
            verif_file = root / "week3_manual_verification.json"
            timing_file.write_text(
                json.dumps({"status": "MEASURED", "elapsed_ms": 5012.3, "case_count": 32}),
                encoding="utf-8",
            )
            verif_file.write_text(
                json.dumps(
                    [
                        *([{"outcome": "CONFIRMED_USER_TO_USER_BOLA", "access_direction": "USER_TO_USER"}] * 4),
                        *([{"outcome": "CONFIRMED_USER_TO_ADMIN_BOLA", "access_direction": "USER_TO_ADMIN"}] * 3),
                        *([{"outcome": "POLICY_DEPENDENT_ADMIN_ACCESS", "access_direction": "ADMIN_TO_USER"}] * 4),
                        {"outcome": "POLICY_DEPENDENT_ADMIN_ACCESS", "access_direction": "ADMIN_TO_ADMIN"},
                    ]
                ),
                encoding="utf-8",
            )
            comparison = build_final_comparison(
                bfla_findings=None,
                zap_report=None,
                script_timing_path=timing_file,
            )
        self.assertEqual(comparison["comparison_scope"]["script_total_cases"], 32)
        self.assertEqual(comparison["custom_script"]["case_count"], 32)
        self.assertEqual(comparison["custom_script"]["confirmed_user_to_user_bola"], 4)
        self.assertEqual(comparison["custom_script"]["confirmed_user_to_admin_bola"], 3)
        self.assertEqual(comparison["custom_script"]["policy_dependent_admin_access"], 5)


    def test_absence_never_invents_counts_or_disclosure(self):
        result = build_final_comparison(None, None, manual_worksheet_path="/missing")
        for key in ("case_count", "confirmed_user_to_user_bola",
                    "confirmed_user_to_admin_bola", "policy_dependent_admin_access",
                    "hidden_200_data_exposure"):
            self.assertIsNone(result["custom_script"][key])
        self.assertIsNone(result["comparison_scope"]["script_total_cases"])

    def test_functional_evidence_survives_missing_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "verification.json"
            source.write_text(json.dumps([{"outcome": "CONFIRMED_USER_TO_USER_BOLA"}]))
            result = build_final_comparison(None, None, verification_path=source)
        self.assertEqual(result["custom_script"]["confirmed_user_to_user_bola"], 1)
        self.assertEqual(result["custom_script"]["functional_status"], "AVAILABLE")
        self.assertEqual(result["custom_script"]["status"], "TIMING_NOT_AVAILABLE")

    def test_malformed_verification_remains_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "verification.json"
            for content in ("{", "{}", "[]", '[{}]', '[null]'):
                source.write_text(content)
                result = build_final_comparison(None, None, verification_path=source)
                self.assertIsNone(result["custom_script"]["confirmed_user_to_user_bola"])

    def test_direct_and_legacy_timing_cannot_bypass_validation(self):
        for elapsed in (float("nan"), float("inf"), -1, True):
            with self.subTest(elapsed=elapsed), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "timing.json"
                source.write_text(json.dumps({"status": "MEASURED", "elapsed_ms": elapsed, "case_count": 12}))
                for kwargs in ({"script_timing_path": source}, {"timing_evidence": TimingEvidence("AVAILABLE", source, elapsed, 12)}):
                    script = build_final_comparison(None, None, **kwargs)["custom_script"]
                    self.assertEqual(script["status"], "TIMING_NOT_AVAILABLE")
                    self.assertIsNone(script["elapsed_ms"])
                    self.assertIsNone(script["case_count"])

    def test_invalid_completion_payloads_fail_closed(self):
        for payload in ({}, {"status": "FAILED"}, {"status": "COMPLETED"},
                        {"status": "COMPLETED", "scan_result_count": True, "unauthorized_access_findings": []}):
            self.assertEqual(build_final_comparison(None, payload)["owasp_zap"]["status"], "INVALID")
        for payload in ({}, {"status": "NOT_RUN"}, {"overall_verdict": "DENIED_CONTROL", "cases": []},
                        {"overall_verdict": "invented", "cases": [{"id": "x", "verdict": "DENIED"}]}):
            self.assertEqual(build_final_comparison(payload, None)["bfla_disposable"]["status"], "INVALID")

    def test_bfla_contradictory_verdict_and_duplicate_cases_are_invalid(self):
        cases = [{"id": "x", "verdict": "BFLA_CONFIRMED"}]
        for payload in (
            {"overall_verdict": "DENIED_CONTROL", "cases": cases},
            {"overall_verdict": "BFLA_CONFIRMED_DESTRUCTIVE", "cases": cases * 2},
            {"status": "NOT_RUN", "overall_verdict": "BFLA_CONFIRMED_DESTRUCTIVE", "cases": cases},
        ):
            self.assertEqual(build_final_comparison(payload, None)["bfla_disposable"]["status"], "INVALID")

    def test_adjacent_search_never_uses_parent_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "week3_manual_verification.json").write_text('[{"outcome": "CONFIRMED_USER_TO_USER_BOLA"}]')
            child = root / "other-run"
            child.mkdir()
            timing = TimingEvidence("AVAILABLE", child / "timing.json", 10, 2)
            result = build_final_comparison(None, None, timing_evidence=timing)
            self.assertIsNone(result["custom_script"]["confirmed_user_to_user_bola"])

    def test_manual_invalid_timing_preserves_functional_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "worksheet.md"
            for timing in ("nan", "inf", "-1"):
                source.write_text("\n".join(f"| M-{i:02d} | GET /a | a | deny | 403 | Denied | {timing} |" for i in range(1, 8)))
                result = _parse_manual_worksheet(source)
                self.assertIsNone(result["elapsed_minutes"])
                self.assertEqual(result["status"], "COMPLETED_NO_TIMING")
                self.assertEqual(result["confirmed_findings"], 0)


class WriteComparisonTests(OfflineTests):
    """Written comparison must pass redaction checks."""

    def test_writes_valid_json(self):
        comparison = build_final_comparison(
            bfla_findings=None,
            zap_report=None,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_comparison(comparison, Path(tmpdir) / "out.json")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["custom_script"]["status"], "TIMING_NOT_AVAILABLE")
        self.assertFalse(
            any("Bearer" in str(v) or "eyJ" in str(v)
                for v in json.dumps(loaded).split())
        )


if __name__ == "__main__":
    unittest.main()
