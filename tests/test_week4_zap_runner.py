"""Tests for the verified-imported-Context ZAP lifecycle."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from week4.zap_context_builder import HistorySnapshot, ZapContextError
from week4.zap_runner import (
    _build_not_run_report,
    _extract_transient_html_summary,
    _poll_scan_status,
    _start_access_control_scan,
    run_zap_access_control,
    run_zap_authentication_bootstrap,
)


class ScanContractTests(unittest.TestCase):
    def test_version_metadata_uses_documented_installed_addons_key(self):
        responses = iter([
            {"version": "2.17.0"},
            {"installedAddons": [{"id": "accessControl", "name": "Access Control Testing", "version": "13.0.0"}]},
        ])
        with patch("week4.zap_runner._zap_api", side_effect=lambda *args, **kwargs: next(responses)):
            from week4.zap_runner import _version_metadata

            metadata = _version_metadata("key")
        self.assertEqual(metadata, {"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"})

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


class TransientHtmlParserTests(unittest.TestCase):
    def test_extracts_exact_reviewed_rows_from_documented_table_layout(self):
        html = """<!doctype html><table>
        <tr><th></th><th></th><th colspan=\"2\">admin</th><th colspan=\"2\">userA</th></tr>
        <tr><th>Method</th><th>URL</th><th>Authorization</th><th>Access Control</th><th>Authorization</th><th>Access Control</th></tr>
        <tr><td>GET</td><td><a href=\"http://127.0.0.1:5000/me\">ignored URL text</a></td><td>Authorized</td><td class=\"VALID\">localized</td><td>Authorized</td><td class=\"ILLEGAL\">localized</td></tr>
        </table>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "temporary.html"
            report_path.write_text(html, encoding="utf-8")
            rows = _extract_transient_html_summary(
                report_path,
                {"allowed_requests": [{"method": "GET", "path": "/me"}]},
                [{"id": "1", "name": "admin"}, {"id": "2", "name": "userA"}],
            )
        self.assertEqual(
            rows,
            [
                {"path": "/me", "user": "admin", "result": "VALID"},
                {"path": "/me", "user": "userA", "result": "ILLEGAL"},
            ],
        )

    def test_rejects_rows_without_exact_reviewed_url_or_result_class(self):
        html = """<table>
        <tr><th></th><th></th><th colspan=\"2\">admin</th></tr>
        <tr><td>GET</td><td><a href=\"http://127.0.0.1:5000/me?unsafe=1\">/me</a></td><td>Authorized</td><td class=\"ILLEGAL\">ILLEGAL</td></tr>
        </table>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "temporary.html"
            report_path.write_text(html, encoding="utf-8")
            with self.assertRaises(ZapContextError):
                _extract_transient_html_summary(
                    report_path,
                    {"allowed_requests": [{"method": "GET", "path": "/me"}]},
                    [{"id": "1", "name": "admin"}],
                )


class RunZapAccessControlTests(unittest.TestCase):
    def setUp(self):
        self.quiescence = patch(
            "week4.zap_runner.wait_for_history_quiescence",
            return_value={
                "required_stable_reads": 2,
                "observation_interval_seconds": 1,
                "timeout_seconds": 10,
            },
        )
        self.quiescence.start()
        self.addCleanup(self.quiescence.stop)

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

    def test_bootstrap_only_verifies_static_desktop_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "bootstrap.json"
            context = Path(tmpdir) / "private.context"
            context.write_bytes(b"reviewed-private-context")
            metadata = {"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}
            context_metadata = {"context_id": "8", "context_name": "vampi-safe-authz", "include_count": 5}
            users = [
                {"id": "1", "name": "admin"},
                {"id": "2", "name": "userA"},
                {"id": "3", "name": "userB"},
            ]
            with patch("week4.zap_runner._version_metadata", return_value=metadata), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.verify_preloaded_context", return_value=context_metadata), \
                 patch("week4.zap_runner.verify_imported_users", return_value=users), \
                 patch("week4.zap_runner.verify_user_authentication_state") as auth_state, \
                 patch("week4.zap_runner.seed_reviewed_paths") as seed, \
                 patch("week4.zap_runner._start_access_control_scan") as scan:
                readiness = run_zap_authentication_bootstrap(
                    context_path=context,
                    context_attestation_path="attestation.json",
                    bootstrap_path=output,
                )
            self.assertEqual(readiness["status"], "BOOTSTRAP_REQUIRES_OPERATOR_AUTH_AND_QUIESCE")
            self.assertEqual(readiness["reviewed_user_names"], ["admin", "userA", "userB"])
            self.assertNotIn("context_id", json.dumps(readiness))
            self.assertEqual(json.loads(output.read_text())["status"], readiness["status"])
            auth_state.assert_not_called()
            seed.assert_not_called()
            scan.assert_not_called()

    def test_bootstrap_rejects_import_mode_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "bootstrap.json"
            with patch("week4.zap_runner._version_metadata") as version, \
                 patch("week4.zap_runner.import_reviewed_context") as import_context, \
                 patch("week4.zap_runner.seed_reviewed_paths") as seed:
                readiness = run_zap_authentication_bootstrap(
                    context_mode="import", bootstrap_path=output
                )
            self.assertEqual(readiness["status"], "BOOTSTRAP_NOT_READY")
            self.assertEqual(readiness["details"]["gate"], "zap_addon")
            version.assert_not_called()
            import_context.assert_not_called()
            seed.assert_not_called()

    def test_quiescence_timeout_stops_before_baseline_seed_or_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            host_report = Path(tmpdir) / "temporary.html"
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.import_reviewed_context", return_value="1"), \
                 patch("week4.zap_runner.verify_imported_context", return_value={"context_id": "1"}), \
                 patch("week4.zap_runner.verify_imported_users", return_value=[{"id": "1", "name": "admin"}]), \
                 patch("week4.zap_runner.verify_user_authentication_state", return_value=[]) as authentication, \
                 patch("week4.zap_runner.wait_for_history_quiescence", side_effect=ZapContextError("ZAP target history did not quiesce before the safe timeout.")) as quiescence, \
                 patch("week4.zap_runner.capture_history_snapshot") as baseline, \
                 patch("week4.zap_runner.seed_reviewed_paths") as seed, \
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
        self.assertEqual(report["reason"], "Post-auth target history quiescence timed out.")
        self.assertEqual(report["details"]["gate"], "post_auth_quiescence")
        authentication.assert_called_once()
        quiescence.assert_called_once()
        baseline.assert_not_called()
        seed.assert_not_called()
        start_scan.assert_not_called()
        self.assertNotIn("Bearer", json.dumps(report))

    def test_preloaded_desktop_uses_loaded_context_without_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            context_path = Path(tmpdir) / "private.context"
            context_path.write_bytes(b"reviewed-private-context")
            host_report = Path(tmpdir) / "temporary.html"
            metadata = {"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}
            context_metadata = {"context_id": "8", "context_name": "vampi-safe-authz", "include_count": 5}
            with patch("week4.zap_runner._version_metadata", return_value=metadata), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.verify_preloaded_context", return_value=context_metadata) as verify_preloaded, \
                 patch("week4.zap_runner.import_reviewed_context") as import_context, \
                 patch("week4.zap_runner.verify_imported_users", return_value=[{"id": "1", "name": "admin"}]), \
                 patch("week4.zap_runner.verify_user_authentication_state", return_value=[]), \
                 patch("week4.zap_runner.capture_history_snapshot", side_effect=[
                     HistorySnapshot({"1": None}), HistorySnapshot({"1": None, "2": "query_or_fragment"}),
                 ]), \
                 patch("week4.zap_runner.verify_seed_delta", return_value=(False, {"new_message_count": 1, "approved_path_counts": {}, "violation_counts": {"query_or_fragment": 1}})), \
                 patch("week4.zap_runner.seed_reviewed_paths", return_value={"seeded_request_count": 0}), \
                 patch("week4.zap_runner.verify_site_tree_containment", return_value=(True, {"other_nodes": 0})), \
                 patch("week4.zap_runner._start_access_control_scan") as start_scan:
                report = run_zap_access_control(
                    context_mode="preloaded-desktop",
                    context_path=context_path,
                    context_attestation_path="attestation.json",
                    host_report_path=host_report,
                    zap_report_path=str(host_report),
                    report_path=report_path,
                    status_path=status_path,
                )
            self.assertEqual(report["status"], "NOT_RUN")
            verify_preloaded.assert_called_once()
            import_context.assert_not_called()
            start_scan.assert_not_called()

    def test_preloaded_desktop_records_bounded_metadata_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            context_path = Path(tmpdir) / "private.context"
            context_path.write_bytes(b"reviewed-private-context")
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.verify_preloaded_context", side_effect=ZapContextError("private failure detail")), \
                 patch("week4.zap_runner.import_reviewed_context") as import_context, \
                 patch("week4.zap_runner.verify_imported_users") as verify_users:
                report = run_zap_access_control(
                    context_mode="preloaded-desktop",
                    context_path=context_path,
                    context_attestation_path="attestation.json",
                    host_report_path=Path(tmpdir) / "temporary.html",
                    zap_report_path="/tmp/temporary.html",
                    report_path=report_path,
                    status_path=status_path,
                )
            self.assertEqual(report["status"], "NOT_RUN")
            self.assertEqual(
                report["details"],
                {
                    "context_mode": "preloaded-desktop",
                    "failure_class": "ZapContextError",
                    "gate": "preloaded_context_metadata",
                },
            )
            self.assertNotIn("private failure detail", json.dumps(report))
            import_context.assert_not_called()
            verify_users.assert_not_called()

    def test_preloaded_desktop_rejects_import_path_before_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": []}), \
                 patch("week4.zap_runner.load_context_attestation") as attestation, \
                 patch("week4.zap_runner.import_reviewed_context") as import_context:
                report = run_zap_access_control(
                    context_mode="preloaded-desktop",
                    context_path="private.context",
                    zap_context_path="/zap/context/private.context",
                    host_report_path=Path(tmpdir) / "temporary.html",
                    zap_report_path="/zap/output/temporary.html",
                    report_path=report_path,
                    status_path=status_path,
                )
            self.assertEqual(report["status"], "NOT_RUN")
            attestation.assert_not_called()
            import_context.assert_not_called()

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
                 patch("week4.zap_runner.capture_history_snapshot", side_effect=[
                     HistorySnapshot({"1": None}), HistorySnapshot({"1": None, "2": "query_or_fragment"}),
                 ]), \
                 patch("week4.zap_runner.seed_reviewed_paths", return_value={"seeded_request_count": 0}), \
                 patch("week4.zap_runner.verify_site_tree_containment", return_value=(True, {"other_nodes": 0})), \
                 patch("week4.zap_runner.verify_seed_delta", return_value=(False, {"new_message_count": 1, "approved_path_counts": {}, "violation_counts": {"query_or_fragment": 1}})), \
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

    def test_failed_transient_report_write_is_not_parsed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            host_report = Path(tmpdir) / "temporary.html"
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [{"method": "GET", "path": "/me"}], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.import_reviewed_context", return_value="1"), \
                 patch("week4.zap_runner.verify_imported_context", return_value={"context_id": "1", "context_name": "vampi-safe-authz", "include_count": 1}), \
                 patch("week4.zap_runner.verify_imported_users", return_value=[{"id": "1", "name": "admin"}]), \
                 patch("week4.zap_runner.verify_user_authentication_state", return_value=[]), \
                 patch("week4.zap_runner.capture_history_snapshot", side_effect=[HistorySnapshot({}), HistorySnapshot({"2": "/me"})]), \
                 patch("week4.zap_runner.seed_reviewed_paths", return_value={"seeded_request_count": 1}), \
                 patch("week4.zap_runner.verify_site_tree_containment", return_value=(True, {"other_nodes": 0})), \
                 patch("week4.zap_runner.verify_seed_delta", return_value=(True, {"new_message_count": 1, "approved_path_counts": {"/me": 1}, "violation_counts": {}})), \
                 patch("week4.zap_runner._start_access_control_scan"), \
                 patch("week4.zap_runner._poll_scan_status", return_value={"progress": 100, "status": "COMPLETED"}), \
                 patch("week4.zap_runner._zap_api", side_effect=ZapContextError("report write failed")), \
                 patch("week4.zap_runner._extract_transient_html_summary") as parse_html:
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
            self.assertEqual(report["details"]["gate"], "transient_report_write")
            parse_html.assert_not_called()
            self.assertFalse(host_report.exists())

    def test_transient_report_requires_exact_write_html_acknowledgement(self):
        malformed_responses = (
            {},
            {"Result": "OK"},
            {"writeHTMLreport": "ERROR"},
            {"writeHTMLreport": "OK", "unexpected": True},
        )
        for malformed_response in malformed_responses:
            with self.subTest(response=malformed_response), tempfile.TemporaryDirectory() as tmpdir:
                report_path, status_path = self._paths(tmpdir)
                host_report = Path(tmpdir) / "temporary.html"
                with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                     patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [{"method": "GET", "path": "/me"}], "context_name": "vampi-safe-authz"}), \
                     patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                     patch("week4.zap_runner.import_reviewed_context", return_value="1"), \
                     patch("week4.zap_runner.verify_imported_context", return_value={"context_id": "1", "context_name": "vampi-safe-authz", "include_count": 1}), \
                     patch("week4.zap_runner.verify_imported_users", return_value=[{"id": "1", "name": "admin"}]), \
                     patch("week4.zap_runner.verify_user_authentication_state", return_value=[]), \
                     patch("week4.zap_runner.capture_history_snapshot", side_effect=[HistorySnapshot({}), HistorySnapshot({"2": "/me"})]), \
                     patch("week4.zap_runner.seed_reviewed_paths", return_value={"seeded_request_count": 1}), \
                     patch("week4.zap_runner.verify_site_tree_containment", return_value=(True, {"other_nodes": 0})), \
                     patch("week4.zap_runner.verify_seed_delta", return_value=(True, {"new_message_count": 1, "approved_path_counts": {"/me": 1}, "violation_counts": {}})), \
                     patch("week4.zap_runner._start_access_control_scan"), \
                     patch("week4.zap_runner._poll_scan_status", return_value={"progress": 100, "status": "COMPLETED"}), \
                     patch("week4.zap_runner._zap_api", return_value=malformed_response), \
                     patch("week4.zap_runner._extract_transient_html_summary") as parse_html:
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
                self.assertEqual(report["details"]["gate"], "transient_report_write")
                parse_html.assert_not_called()

    def test_transient_report_path_must_be_absolute_for_zap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation") as attestation:
                report = run_zap_access_control(
                    context_path="private.context",
                    zap_context_path="/zap/wrk/private.context",
                    context_attestation_path="attestation.json",
                    host_report_path=Path(tmpdir) / "temporary.html",
                    zap_report_path="relative-report.html",
                    report_path=report_path,
                    status_path=status_path,
                )
            self.assertEqual(report["status"], "NOT_RUN")
            self.assertEqual(report["details"]["gate"], "input_contract")
            attestation.assert_not_called()

    def test_transient_report_path_cannot_overlap_artifact_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation") as attestation:
                report = run_zap_access_control(
                    context_path="private.context",
                    zap_context_path="/zap/wrk/private.context",
                    context_attestation_path="attestation.json",
                    host_report_path=report_path,
                    zap_report_path="/zap/wrk/temporary.html",
                    report_path=report_path,
                    status_path=status_path,
                )
            self.assertEqual(report["status"], "NOT_RUN")
            self.assertEqual(report["details"]["gate"], "input_contract")
            attestation.assert_not_called()

    def test_existing_transient_report_path_stops_before_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            host_report = Path(tmpdir) / "temporary.html"
            host_report.write_text("untrusted stale contents", encoding="utf-8")
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation") as attestation, \
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
            self.assertEqual(report["details"]["gate"], "input_contract")
            self.assertTrue(host_report.exists())
            attestation.assert_not_called()
            start_scan.assert_not_called()

    def test_quiescence_metadata_is_in_completed_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            host_report = Path(tmpdir) / "temporary.html"
            snapshots = [
                HistorySnapshot({}),
                HistorySnapshot({"2": "/me"}),
                HistorySnapshot({"2": "/me"}),
            ]
            quiescence = {
                "required_stable_reads": 2,
                "observation_interval_seconds": 1,
                "timeout_seconds": 10,
            }
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [{"method": "GET", "path": "/me"}], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.import_reviewed_context", return_value="1"), \
                 patch("week4.zap_runner.verify_imported_context", return_value={"context_id": "1", "context_name": "vampi-safe-authz", "include_count": 1}), \
                 patch("week4.zap_runner.verify_imported_users", return_value=[{"id": "1", "name": "admin"}]), \
                 patch("week4.zap_runner.verify_user_authentication_state", return_value=[]), \
                 patch("week4.zap_runner.wait_for_history_quiescence", return_value=quiescence), \
                 patch("week4.zap_runner.capture_history_snapshot", side_effect=snapshots), \
                 patch("week4.zap_runner.seed_reviewed_paths", return_value={"seeded_request_count": 1}), \
                 patch("week4.zap_runner.verify_site_tree_containment", return_value=(True, {"other_nodes": 0})), \
                 patch("week4.zap_runner.verify_seed_delta", return_value=(True, {"new_message_count": 1, "approved_path_counts": {"/me": 1}, "violation_counts": {}})), \
                 patch("week4.zap_runner._start_access_control_scan"), \
                 patch("week4.zap_runner._poll_scan_status", return_value={"progress": 100, "status": "COMPLETED"}), \
                 patch("week4.zap_runner._zap_api", return_value={"writeHTMLreport": "OK"}), \
                 patch("week4.zap_runner._extract_transient_html_summary", return_value=[{"path": "/me", "user": "admin", "result": "VALID"}]), \
                 patch("week4.zap_runner.verify_history_delta", return_value=(True, {"new_message_count": 0, "approved_path_counts": {"/me": 0}, "violation_counts": {}})):
                report = run_zap_access_control(
                    context_path="private.context",
                    zap_context_path="/zap/wrk/private.context",
                    context_attestation_path="attestation.json",
                    host_report_path=host_report,
                    zap_report_path="/zap/wrk/temporary.html",
                    report_path=report_path,
                    status_path=status_path,
                )
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["scan_metadata"]["quiescence"], quiescence)
        self.assertNotIn("Bearer", json.dumps(report))
        self.assertNotIn('"1"', json.dumps(report["scan_metadata"]["quiescence"]))

    def test_post_scan_delta_failure_never_returns_completed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, status_path = self._paths(tmpdir)
            host_report = Path(tmpdir) / "temporary.html"
            snapshots = [
                HistorySnapshot({"1": None}),
                HistorySnapshot({"1": None, "2": "/me"}),
                HistorySnapshot({"1": None, "2": "/me", "3": "non_get_method"}),
            ]
            with patch("week4.zap_runner._version_metadata", return_value={"zap_version": "2.17.0", "access_control_addon_version": "13.0.0"}), \
                 patch("week4.zap_runner.load_allowlist_v2", return_value={"allowed_requests": [{"method": "GET", "path": "/me"}], "context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.load_context_attestation", return_value={"context_name": "vampi-safe-authz"}), \
                 patch("week4.zap_runner.import_reviewed_context", return_value="1"), \
                 patch("week4.zap_runner.verify_imported_context", return_value={"context_id": "1", "context_name": "vampi-safe-authz", "include_count": 1}), \
                 patch("week4.zap_runner.verify_imported_users", return_value=[{"id": "1", "name": "admin"}]), \
                 patch("week4.zap_runner.verify_user_authentication_state", return_value=[]), \
                 patch("week4.zap_runner.capture_history_snapshot", side_effect=snapshots), \
                 patch("week4.zap_runner.seed_reviewed_paths", return_value={"seeded_request_count": 1}), \
                 patch("week4.zap_runner.verify_site_tree_containment", return_value=(True, {"other_nodes": 0})), \
                 patch("week4.zap_runner.verify_seed_delta", return_value=(True, {"new_message_count": 1, "approved_path_counts": {"/me": 1}, "violation_counts": {}})), \
                 patch("week4.zap_runner._start_access_control_scan"), \
                 patch("week4.zap_runner._poll_scan_status", return_value={"progress": 100, "status": "COMPLETED"}), \
                 patch("week4.zap_runner._zap_api", return_value={"writeHTMLreport": "OK"}), \
                 patch("week4.zap_runner._extract_transient_html_summary", return_value=[{"path": "/me", "user": "admin", "result": "VALID"}]), \
                 patch("week4.zap_runner.verify_history_delta", return_value=(False, {"new_message_count": 1, "approved_path_counts": {"/me": 0}, "violation_counts": {"non_get_method": 1}})):
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
            self.assertIn("Post-scan", report["reason"])
            persisted = report_path.read_text(encoding="utf-8")
            self.assertNotIn('"1"', persisted)
            self.assertNotIn("Bearer", persisted)

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
