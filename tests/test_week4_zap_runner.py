"""Tests for the verified-imported-Context ZAP lifecycle."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from week4.zap_context_builder import ZapContextError
from week4.zap_runner import (
    _build_not_run_report,
    _poll_scan_status,
    _start_access_control_scan,
    run_zap_access_control,
)


class ScanContractTests(unittest.TestCase):
    def test_start_uses_context_and_comma_separated_user_ids(self):
        calls = []

        def fake_api(component, action_type, action, params=None, *, api_key=""):
            calls.append((component, action_type, action, params))
            return {"Result": "OK"}

        users = [{"id": "3", "name": "admin"}, {"id": "4", "name": "userA"}]
        with patch("week4.zap_runner._zap_api", side_effect=fake_api):
            result = _start_access_control_scan("key", "8", users)
        self.assertIsNone(result)
        self.assertEqual(calls[0][3]["contextId"], "8")
        self.assertEqual(calls[0][3]["userId"], "3,4")
        self.assertEqual(calls[0][3]["raiseAlert"], "false")

    def test_start_requires_ok_response_without_scan_id(self):
        with patch("week4.zap_runner._zap_api", return_value={"Result": "ERROR"}):
            with self.assertRaises(ZapContextError):
                _start_access_control_scan("", "8", [{"id": "3", "name": "admin"}])

    def test_poll_uses_context_id_and_completes(self):
        responses = iter([
            {"getScanProgress": "42"}, {"getScanStatus": "RUNNING"},
            {"getScanProgress": "100"}, {"getScanStatus": "NOT RUNNING"},
        ])
        with patch("week4.zap_runner._zap_api", side_effect=lambda *args, **kwargs: next(responses)), \
             patch("week4.zap_runner.time.sleep"):
            result = _poll_scan_status("", "8", timeout=5)
        self.assertEqual(result, {"progress": 100, "status": "NOT RUNNING"})

    def test_poll_rejects_interrupted_scan(self):
        responses = iter([{"getScanProgress": "10"}, {"getScanStatus": "INTERRUPTED"}])
        with patch("week4.zap_runner._zap_api", side_effect=lambda *args, **kwargs: next(responses)):
            with self.assertRaises(ZapContextError):
                _poll_scan_status("", "8", timeout=5)


class RunZapAccessControlTests(unittest.TestCase):
    def _paths(self, tmpdir):
        return Path(tmpdir) / "report.json", Path(tmpdir) / "status.json"

    def test_missing_imported_context_stops_before_context_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            metadata = {"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}
            with patch("week4.zap_runner._version_metadata", return_value=metadata), \
                 patch("week4.zap_runner.import_reviewed_context") as import_context:
                report = run_zap_access_control(
                    report_path=report_path,
                    status_path=status_path,
                    context_path=None,
                )
            self.assertEqual(report["status"], "NOT_RUN")
            import_context.assert_not_called()
            self.assertEqual(json.loads(status_path.read_text())["status"], "NOT_RUN")

    def test_pre_scan_history_failure_never_starts_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            host_report = Path(tmpdir) / "temporary.html"
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.import_reviewed_context", return_value="1"), \
                 patch("week4.zap_runner.verify_imported_context", return_value={"context_id": "1"}), \
                 patch("week4.zap_runner.verify_imported_users", return_value=[{"id": "1", "name": "admin"}]), \
                 patch("week4.zap_runner.verify_user_authentication_state", return_value=[]), \
                 patch("week4.zap_runner.seed_reviewed_paths", return_value={"seeded_request_count": 0}), \
                 patch("week4.zap_runner.verify_site_tree_containment", return_value=(True, {"other_nodes": 0})), \
                 patch("week4.zap_runner.verify_message_containment", side_effect=[
                     (True, {"message_count": 0, "violation_counts": {}}),
                     (False, {"message_count": 1, "violation_counts": {"query_or_fragment": 1}}),
                 ]), \
                 patch("week4.zap_runner._start_access_control_scan") as start_scan:
                report = run_zap_access_control(
                    context_path="private.context",
                    zap_context_path="/zap/wrk/private.context",
                    context_attestation_path="attestation.json",
                    host_report_path=host_report,
                    zap_report_path="/zap/wrk/temporary.html",
                    report_path=report_path,
                    status_path=status_path,
                )
            self.assertEqual(report["status"], "NOT_RUN")
            self.assertIn("Pre-scan", report["reason"])
            start_scan.assert_not_called()
            self.assertNotIn("Bearer", report_path.read_text())

    def test_not_run_report_has_no_raw_error_or_credentials(self):
        report = _build_not_run_report("Safe stop", details={"failure_class": "ZapContextError"})
        self.assertEqual(report["status"], "NOT_RUN")
        self.assertNotIn("Bearer", json.dumps(report))
        self.assertNotIn("responseHeader", json.dumps(report))

    def test_caller_status_path_does_not_mutate_default_status_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            with patch("week4.zap_runner._version_metadata", side_effect=ZapContextError("offline")):
                run_zap_access_control(report_path=report_path, status_path=status_path)
            written = json.loads(status_path.read_text())
        self.assertEqual(written["status"], "NOT_RUN")
        self.assertEqual(written["reason"], "Safety gate stopped the Access Control assessment: ZapContextError.")


if __name__ == "__main__":
    unittest.main()
