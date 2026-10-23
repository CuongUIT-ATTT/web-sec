"""Tests for strict Week 4 ZAP Context and request-history guardrails."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from week4.zap_context_builder import (
    TARGET_BASE,
    ZapContextError,
    _classify_request_header,
    allowed_paths,
    get_messages_in_scope,
    seed_reviewed_paths,
    load_allowlist_v2,
    load_context_attestation,
    verify_imported_users,
    verify_message_containment,
    verify_site_tree_containment,
)


class AllowlistV2Tests(unittest.TestCase):
    def _write_manifest(self, tmpdir, overrides=None):
        manifest = {
            "schema_version": 2,
            "assessment_id": "zap-access-control-v2",
            "target": TARGET_BASE,
            "context_name": "vampi-safe-authz",
            "allowed_requests": [
                {"method": "GET", "path": "/books/v1/week1-userA-book"},
            ],
            "prohibitions": ["/createdb", "POST", "PUT", "PATCH", "DELETE"],
        }
        if overrides:
            manifest.update(overrides)
        path = Path(tmpdir) / "allowlist.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_accepts_local_get_manifest_schema_two(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = load_allowlist_v2(self._write_manifest(tmpdir))
        self.assertEqual(allowed_paths(manifest), {"/books/v1/week1-userA-book"})

    def test_rejects_query_createdb_and_non_get(self):
        bad_requests = (
            {"method": "GET", "path": "/createdb"},
            {"method": "GET", "path": "/books/v1/a?x=1"},
            {"method": "DELETE", "path": "/books/v1/a"},
        )
        for request in bad_requests:
            with self.subTest(request=request), tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(ZapContextError):
                    load_allowlist_v2(self._write_manifest(tmpdir, {"allowed_requests": [request]}))


class MessageContainmentTests(unittest.TestCase):
    def _manifest(self):
        return {
            "target": TARGET_BASE,
            "allowed_requests": [{"method": "GET", "path": "/books/v1/week1-userA-book"}],
        }

    def test_exact_approved_get_is_accepted(self):
        result = _classify_request_header(
            "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1\r\nAuthorization: " + "Bearer " + "secret",
            self._manifest(),
        )
        self.assertIsNone(result)

    def test_unsafe_or_malformed_request_lines_fail_closed(self):
        cases = {
            "missing": None,
            "malformed": "GET only-two-fields",
            "non-get": "POST http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1",
            "query": "GET http://127.0.0.1:5000/books/v1/week1-userA-book?x=1 HTTP/1.1",
            "fragment": "GET http://127.0.0.1:5000/books/v1/week1-userA-book#x HTTP/1.1",
            "wrong-origin": "GET https://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1",
            "wrong-port": "GET http://127.0.0.1:5001/books/v1/week1-userA-book HTTP/1.1",
            "createdb": "GET http://127.0.0.1:5000/createdb HTTP/1.1",
            "unapproved": "GET http://127.0.0.1:5000/books/v1/other HTTP/1.1",
        }
        for label, header in cases.items():
            with self.subTest(label=label):
                self.assertIsNotNone(_classify_request_header(header, self._manifest()))

    def test_pagination_walks_every_message(self):
        calls = []

        def fake_api(component, action_type, action, params=None, *, api_key=""):
            calls.append((action, params))
            if action == "numberOfMessages":
                return {"numberOfMessages": "101"}
            if action == "messages":
                start = int(params["start"])
                count = int(params["count"])
                return {"messages": [{"requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1"}] * count}
            self.fail(action)

        with patch("week4.zap_context_builder._zap_api", side_effect=fake_api):
            messages = get_messages_in_scope("")
        self.assertEqual(len(messages), 101)
        self.assertEqual([params["start"] for action, params in calls if action == "messages"], ["0", "100"])

    def test_history_summary_never_exports_header_content(self):
        messages = [{"requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1\r\nAuthorization: " + "Bearer " + "should-not-export"}]
        with patch("week4.zap_context_builder.get_messages_in_scope", return_value=messages):
            contained, details = verify_message_containment("", self._manifest())
        self.assertTrue(contained)
        self.assertNotIn("Bearer", json.dumps(details))
        self.assertNotIn("Authorization", json.dumps(details))

    def test_seed_calls_access_url_only_for_approved_paths(self):
        calls = []

        def fake_api(component, action_type, action, params=None, *, api_key=""):
            calls.append(params["url"])
            return {"Result": "OK"}

        manifest = {
            "allowed_requests": [
                {"method": "GET", "path": "/books/v1/week1-userA-book"},
                {"method": "GET", "path": "/me"},
            ]
        }
        with patch("week4.zap_context_builder._zap_api", side_effect=fake_api):
            details = seed_reviewed_paths("", manifest)
        self.assertEqual(details, {"seeded_request_count": 2})
        self.assertEqual(set(calls), {
            f"{TARGET_BASE}/books/v1/week1-userA-book", f"{TARGET_BASE}/me",
        })


class SiteTreeDiagnosticTests(unittest.TestCase):
    def test_parent_nodes_are_diagnostic_not_blocking(self):
        manifest = {
            "target": TARGET_BASE,
            "allowed_requests": [{"method": "GET", "path": "/books/v1/week1-userA-book"}],
        }
        sites = [TARGET_BASE, f"{TARGET_BASE}/books", f"{TARGET_BASE}/books/v1", f"{TARGET_BASE}/unrelated"]
        with patch("week4.zap_context_builder.get_site_tree_urls", return_value=sites):
            contained, diagnostics = verify_site_tree_containment("", manifest)
        self.assertTrue(contained)
        self.assertEqual(diagnostics["structural_parent_nodes"], 3)
        self.assertEqual(diagnostics["other_nodes"], 1)


class ImportedContextAttestationTests(unittest.TestCase):
    def _manifest(self):
        return {
            "context_name": "vampi-safe-authz",
            "allowed_requests": [
                {"method": "GET", "path": "/books/v1/week1-userA-book"},
            ],
        }

    def _attestation(self, fingerprint):
        return {
            "schema_version": 1,
            "context_name": "vampi-safe-authz",
            "target": TARGET_BASE,
            "context_sha256": fingerprint,
            "reviewed_users": ["admin", "userA", "userB"],
            "reviewed_paths": ["/books/v1/week1-userA-book"],
            "access_rule_expectations": {
                "/books/v1/week1-userA-book": {
                    "admin": "policy-dependent", "userA": "allowed", "userB": "denied",
                }
            },
            "reviewed_on": "2026-10-23",
            "reviewer": "local-lab-operator",
        }

    def test_attestation_requires_private_fingerprint_matched_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Path(tmpdir) / "safe.context"
            context.write_bytes(b"reviewed-private-context")
            os.chmod(context, 0o600)
            attestation = Path(tmpdir) / "attestation.json"
            attestation.write_text(json.dumps(self._attestation(hashlib.sha256(context.read_bytes()).hexdigest())), encoding="utf-8")
            loaded = load_context_attestation(attestation, self._manifest(), context)
        self.assertEqual(loaded["context_name"], "vampi-safe-authz")

    def test_attestation_rejects_insecure_context_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Path(tmpdir) / "safe.context"
            context.write_bytes(b"reviewed-private-context")
            os.chmod(context, 0o644)
            attestation = Path(tmpdir) / "attestation.json"
            attestation.write_text(json.dumps(self._attestation("0" * 64)), encoding="utf-8")
            with self.assertRaises(ZapContextError):
                load_context_attestation(attestation, self._manifest(), context)

    def test_users_must_be_exact_enabled_and_unique(self):
        attestation = {"reviewed_users": ["admin", "userA", "userB"]}
        valid = {"users": [
            {"id": "1", "name": "admin", "enabled": "true"},
            {"id": "2", "name": "userA", "enabled": "true"},
            {"id": "3", "name": "userB", "enabled": "true"},
        ]}
        with patch("week4.zap_context_builder._zap_api", return_value=valid):
            users = verify_imported_users("", "7", attestation)
        self.assertEqual([user["name"] for user in users], ["admin", "userA", "userB"])
        valid["users"][2]["enabled"] = "false"
        with patch("week4.zap_context_builder._zap_api", return_value=valid):
            with self.assertRaises(ZapContextError):
                verify_imported_users("", "7", attestation)


if __name__ == "__main__":
    unittest.main()
