"""Tests for strict Week 4 ZAP Context and request-history guardrails."""

import hashlib
import json
import os
import re
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
    capture_history_snapshot,
    get_messages_in_scope,
    history_baseline_summary,
    seed_reviewed_paths,
    load_allowlist_v2,
    load_context_attestation,
    verify_imported_context,
    verify_preloaded_context,
    verify_imported_users,
    verify_user_authentication_state,
    verify_history_delta,
    verify_seed_delta,
    wait_for_history_quiescence,
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


class ImportedContextLookupTests(unittest.TestCase):
    def test_users_list_uses_documented_response_key(self):
        attestation = {"reviewed_users": ["admin", "userA", "userB"]}
        response = {
            "usersList": [
                {"id": "1", "name": "admin", "enabled": "true"},
                {"id": "2", "name": "userA", "enabled": "true"},
                {"id": "3", "name": "userB", "enabled": "true"},
            ]
        }
        with patch("week4.zap_context_builder._zap_api", return_value=response):
            users = verify_imported_users("key", "7", attestation)
        self.assertEqual([user["name"] for user in users], ["admin", "userA", "userB"])

    def test_context_lookup_uses_reviewed_context_name(self):
        calls = []
        manifest = {
            "allowed_requests": [{"method": "GET", "path": "/books/v1/week1-userA-book"}],
        }
        attestation = {"context_name": "vampi-safe-authz"}

        def fake_api(component, action_type, action, params=None, *, api_key=""):
            calls.append((component, action_type, action, params))
            if action == "context":
                return {"context": {"id": "7", "name": "vampi-safe-authz"}}
            if action == "includeRegexs":
                return {"includeRegexs": [(re.escape(TARGET_BASE) + re.escape("/books/v1/week1-userA-book") + "$").replace(r"\-", "-")]}
            self.fail(action)

        with patch("week4.zap_context_builder._zap_api", side_effect=fake_api):
            verified = verify_imported_context("key", "7", manifest, attestation)

        self.assertEqual(verified["context_id"], "7")
        self.assertEqual(calls[0][3], {"contextName": "vampi-safe-authz"})

    def test_preloaded_context_resolves_only_the_attested_name(self):
        calls = []
        manifest = {
            "allowed_requests": [{"method": "GET", "path": "/books/v1/week1-userA-book"}],
        }
        attestation = {"context_name": "vampi-safe-authz"}

        def fake_api(component, action_type, action, params=None, *, api_key=""):
            calls.append((component, action_type, action, params))
            if action == "context":
                return {"context": {"id": "9", "name": "vampi-safe-authz"}}
            if action == "includeRegexs":
                return {"includeRegexs": [(re.escape(TARGET_BASE) + re.escape("/books/v1/week1-userA-book") + "$ ").strip().replace(r"\-", "-")]}
            self.fail(action)

        with patch("week4.zap_context_builder._zap_api", side_effect=fake_api):
            verified = verify_preloaded_context("key", manifest, attestation)

        self.assertEqual(verified["context_id"], "9")
        self.assertEqual(calls[0], ("context", "view", "context", {"contextName": "vampi-safe-authz"}))
        self.assertNotIn("importContext", [call[2] for call in calls])

    def test_authentication_state_accepts_legacy_wrapped_poll_result(self):
        users = [{"id": "1", "name": "admin"}]
        for poll_result in (True, "true"):
            with self.subTest(poll_result=poll_result), patch(
                "week4.zap_context_builder._zap_api",
                return_value={"authenticationState": {"lastPollResult": poll_result}},
            ):
                states = verify_user_authentication_state("key", "7", users)
            self.assertEqual(states, [{"name": "admin", "state": "authenticated"}])

    def test_authentication_state_accepts_current_desktop_top_level_shape(self):
        users = [{"id": "1", "name": "admin"}]
        for poll_result in (True, "true"):
            response = {
                "lastAuthFailure": "false",
                "lastAuthHistoryId": "12",
                "lastPollResult": poll_result,
                "lastPollTimeInMs": "1",
                "lastSuccessfulAuthTimeInMs": "1",
                "requestsSinceLastPoll": "0",
            }
            with self.subTest(poll_result=poll_result), patch(
                "week4.zap_context_builder._zap_api", return_value=response
            ):
                states = verify_user_authentication_state("key", "7", users)
            self.assertEqual(states, [{"name": "admin", "state": "authenticated"}])

    def test_authentication_state_rejects_malformed_negative_or_ambiguous_shapes(self):
        users = [{"id": "1", "name": "admin"}]
        desktop_state = {
            "lastAuthFailure": "false",
            "lastAuthHistoryId": "12",
            "lastPollResult": "true",
            "lastPollTimeInMs": "1",
            "lastSuccessfulAuthTimeInMs": "1",
            "requestsSinceLastPoll": "0",
        }
        cases = (
            {"authenticationState": {}},
            {"authenticationState": {"lastPollResult": "false"}},
            {"authenticationState": {"lastPollResult": "TRUE"}},
            {"authenticationState": "true"},
            {"lastPollResult": "true"},
            {key: value for key, value in desktop_state.items() if key != "lastAuthFailure"},
            {**desktop_state, "lastPollResult": "false"},
            {**desktop_state, "unexpected": "value"},
            {**desktop_state, "authenticationState": {"lastPollResult": "true"}},
        )
        for response in cases:
            with self.subTest(response=response), patch(
                "week4.zap_context_builder._zap_api", return_value=response
            ):
                with self.assertRaises(ZapContextError):
                    verify_user_authentication_state("key", "7", users)

    def test_authentication_state_fails_without_a_partial_multi_user_result(self):
        users = [{"id": "1", "name": "admin"}, {"id": "2", "name": "userA"}]
        responses = [
            {"authenticationState": {"lastPollResult": "true"}},
            {"authenticationState": {"lastPollResult": "false"}},
        ]
        with patch("week4.zap_context_builder._zap_api", side_effect=responses) as zap_api:
            with self.assertRaises(ZapContextError):
                verify_user_authentication_state("key", "7", users)
        self.assertEqual(zap_api.call_count, 2)

    def test_imported_context_requires_exact_id_and_include_regexes(self):
        manifest = {
            "allowed_requests": [{"method": "GET", "path": "/books/v1/week1-userA-book"}],
        }
        attestation = {"context_name": "vampi-safe-authz"}
        expected_regex = re.escape(TARGET_BASE) + re.escape("/books/v1/week1-userA-book") + "$"

        def valid_api(component, action_type, action, params=None, *, api_key=""):
            if action == "context":
                return {"context": {"id": "7", "name": "vampi-safe-authz"}}
            if action == "includeRegexs":
                return {"includeRegexs": [expected_regex.replace(r"\-", "-")]}
            self.fail(action)

        with patch("week4.zap_context_builder._zap_api", side_effect=valid_api):
            verified = verify_imported_context("key", "7", manifest, attestation)
        self.assertEqual(verified["include_count"], 1)
        with patch("week4.zap_context_builder._zap_api", side_effect=valid_api):
            with self.assertRaises(ZapContextError):
                verify_imported_context("key", "8", manifest, attestation)

    def test_context_rejects_duplicate_include_regexes(self):
        manifest = {
            "allowed_requests": [{"method": "GET", "path": "/books/v1/week1-userA-book"}],
        }
        attestation = {"context_name": "vampi-safe-authz"}
        expected_regex = re.escape(TARGET_BASE) + re.escape("/books/v1/week1-userA-book") + "$"

        def duplicate_regex_api(component, action_type, action, params=None, *, api_key=""):
            if action == "context":
                return {"context": {"id": "7", "name": "vampi-safe-authz"}}
            if action == "includeRegexs":
                return {"includeRegexs": [expected_regex.replace(r"\-", "-")] * 2}
            self.fail(action)

        with patch("week4.zap_context_builder._zap_api", side_effect=duplicate_regex_api):
            with self.assertRaises(ZapContextError):
                verify_imported_context("key", "7", manifest, attestation)

    def test_preloaded_context_rejects_name_mismatch(self):
        manifest = {
            "allowed_requests": [{"method": "GET", "path": "/books/v1/week1-userA-book"}],
        }
        attestation = {"context_name": "vampi-safe-authz"}
        with patch(
            "week4.zap_context_builder._zap_api",
            return_value={"context": {"id": "9", "name": "other-context"}},
        ):
            with self.assertRaises(ZapContextError):
                verify_preloaded_context("key", manifest, attestation)


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
                return {"messages": [
                    {
                        "id": str(start + offset + 1),
                        "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1",
                    }
                    for offset in range(count)
                ]}
            self.fail(action)

        with patch("week4.zap_context_builder._zap_api", side_effect=fake_api):
            messages = get_messages_in_scope("")
        self.assertEqual(len(messages), 101)
        self.assertEqual([params["start"] for action, params in calls if action == "messages"], ["0", "100"])

    def test_history_quiescence_accepts_two_equal_target_counts(self):
        clock = iter([0, 0, 1])
        with patch("week4.zap_context_builder._message_count", side_effect=[17, 17]), \
             patch("week4.zap_context_builder.time.monotonic", side_effect=lambda: next(clock)), \
             patch("week4.zap_context_builder.time.sleep") as sleep:
            summary = wait_for_history_quiescence("key")
        self.assertEqual(
            summary,
            {
                "required_stable_reads": 2,
                "observation_interval_seconds": 1,
                "timeout_seconds": 10,
            },
        )
        sleep.assert_called_once_with(1)
        self.assertNotIn("17", json.dumps(summary))

    def test_history_quiescence_retries_until_a_later_stable_pair(self):
        clock = iter([0, 0, 1, 1, 2])
        with patch("week4.zap_context_builder._message_count", side_effect=[3, 4, 4]), \
             patch("week4.zap_context_builder.time.monotonic", side_effect=lambda: next(clock)), \
             patch("week4.zap_context_builder.time.sleep") as sleep:
            summary = wait_for_history_quiescence("key")
        self.assertEqual(summary["required_stable_reads"], 2)
        self.assertEqual(sleep.call_count, 2)

    def test_history_quiescence_fails_closed_at_deadline(self):
        clock = iter([0, 0, 9.5])
        with patch("week4.zap_context_builder._message_count", side_effect=[3, 4]), \
             patch("week4.zap_context_builder.time.monotonic", side_effect=lambda: next(clock)), \
             patch("week4.zap_context_builder.time.sleep") as sleep:
            with self.assertRaisesRegex(ZapContextError, "did not quiesce"):
                wait_for_history_quiescence("key")
        sleep.assert_called_once_with(1)

    def test_history_quiescence_propagates_invalid_count(self):
        with patch("week4.zap_context_builder._message_count", side_effect=ZapContextError("invalid count")), \
             patch("week4.zap_context_builder.time.sleep") as sleep:
            with self.assertRaisesRegex(ZapContextError, "invalid count"):
                wait_for_history_quiescence("key")
        sleep.assert_not_called()

    def test_snapshot_delta_accepts_hidden_baseline_without_exporting_headers(self):
        manifest = self._manifest()
        baseline_messages = [{
            "id": "1",
            "requestHeader": "POST http://127.0.0.1:5000/users/v1/login HTTP/1.1\r\nAuthorization: " + "Bearer " + "should-not-export",
        }]
        seed_messages = baseline_messages + [{
            "id": "2",
            "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1",
        }]
        with patch("week4.zap_context_builder.get_messages_in_scope", side_effect=[baseline_messages, baseline_messages, seed_messages, seed_messages]):
            baseline = capture_history_snapshot("", manifest)
            successor = capture_history_snapshot("", manifest)
        contained, details = verify_history_delta(baseline, successor, manifest)
        self.assertTrue(contained)
        self.assertEqual(details["new_message_count"], 1)
        self.assertEqual(history_baseline_summary(baseline), {"message_count": 1})
        self.assertNotIn("Bearer", json.dumps(details))
        self.assertNotIn("Authorization", json.dumps(details))
        self.assertNotIn("users/v1/login", json.dumps(details))

    def test_snapshot_rejects_duplicate_or_invalid_identities(self):
        manifest = self._manifest()
        duplicate = [
            {"id": "1", "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1"},
            {"id": "1", "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1"},
        ]
        invalid = [{"id": "01", "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1"}]
        boolean = [{"id": True, "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1"}]
        for messages in (duplicate, invalid, boolean):
            with self.subTest(messages=messages), patch("week4.zap_context_builder.get_messages_in_scope", return_value=messages):
                with self.assertRaises(ZapContextError):
                    capture_history_snapshot("", manifest)

    def test_delta_rejects_changed_predecessor_classification(self):
        manifest = self._manifest()
        baseline_messages = [{
            "id": "1",
            "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1",
        }]
        changed_messages = [{
            "id": "1",
            "requestHeader": "POST http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1",
        }]
        with patch("week4.zap_context_builder.get_messages_in_scope", side_effect=[baseline_messages, baseline_messages, changed_messages, changed_messages]):
            baseline = capture_history_snapshot("", manifest)
            changed = capture_history_snapshot("", manifest)
        with self.assertRaises(ZapContextError):
            verify_history_delta(baseline, changed, manifest)

    def test_seed_delta_requires_one_exact_get_per_path(self):
        manifest = {
            "allowed_requests": [
                {"method": "GET", "path": "/books/v1/week1-userA-book"},
                {"method": "GET", "path": "/me"},
            ]
        }
        baseline_messages = [{"id": "1", "requestHeader": "POST http://127.0.0.1:5000/users/v1/login HTTP/1.1"}]
        valid_seed_messages = baseline_messages + [
            {"id": "2", "requestHeader": "GET http://127.0.0.1:5000/books/v1/week1-userA-book HTTP/1.1"},
            {"id": "3", "requestHeader": "GET http://127.0.0.1:5000/me HTTP/1.1"},
        ]
        duplicate_seed_messages = valid_seed_messages + [
            {"id": "4", "requestHeader": "GET http://127.0.0.1:5000/me HTTP/1.1"},
        ]
        with patch("week4.zap_context_builder.get_messages_in_scope", side_effect=[baseline_messages, baseline_messages, valid_seed_messages, valid_seed_messages]):
            baseline = capture_history_snapshot("", manifest)
            valid = capture_history_snapshot("", manifest)
        self.assertTrue(verify_seed_delta(baseline, valid, manifest)[0])
        with patch("week4.zap_context_builder.get_messages_in_scope", side_effect=[baseline_messages, baseline_messages, duplicate_seed_messages, duplicate_seed_messages]):
            baseline = capture_history_snapshot("", manifest)
            duplicate = capture_history_snapshot("", manifest)
        self.assertFalse(verify_seed_delta(baseline, duplicate, manifest)[0])

    def test_seed_calls_access_url_only_for_approved_paths(self):
        calls = []

        def fake_api(component, action_type, action, params=None, *, api_key=""):
            calls.append(params["url"])
            return {"accessUrl": ["opaque"]}

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
        self.assertNotIn("opaque", json.dumps(details))

    def test_seed_rejects_malformed_access_url_response(self):
        manifest = {
            "allowed_requests": [{"method": "GET", "path": "/me"}],
        }
        malformed_responses = (
            None,
            "error",
            {"Result": "OK"},
            {},
            {"accessUrl": None},
            {"accessUrl": ["opaque"], "unexpected": True},
        )
        for response in malformed_responses:
            with self.subTest(response_type=type(response).__name__), patch(
                "week4.zap_context_builder._zap_api", return_value=response
            ):
                with self.assertRaisesRegex(ZapContextError, "seed response"):
                    seed_reviewed_paths("", manifest)


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
                {
                    "method": "GET",
                    "path": "/books/v1/week1-userA-book",
                    "authorization_expectations": {
                        "admin": "policy-dependent",
                        "userA": "allowed",
                        "userB": "denied",
                    },
                },
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

    def test_attestation_rejects_policy_or_audit_metadata_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Path(tmpdir) / "safe.context"
            context.write_bytes(b"reviewed-private-context")
            os.chmod(context, 0o600)
            fingerprint = hashlib.sha256(context.read_bytes()).hexdigest()
            for label, mutate in (
                ("matrix", lambda data: data["access_rule_expectations"]["/books/v1/week1-userA-book"].update({"userB": "allowed"})),
                ("date", lambda data: data.update({"reviewed_on": "2999-01-01"})),
                ("reviewer", lambda data: data.update({"reviewer": "line\\nbreak"})),
            ):
                with self.subTest(label=label):
                    data = self._attestation(fingerprint)
                    mutate(data)
                    attestation = Path(tmpdir) / f"{label}.json"
                    attestation.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ZapContextError):
                        load_context_attestation(attestation, self._manifest(), context)

    def test_users_must_be_exact_enabled_and_unique(self):
        attestation = {"reviewed_users": ["admin", "userA", "userB"]}
        valid = {"usersList": [
            {"id": "1", "name": "admin", "enabled": "true"},
            {"id": "2", "name": "userA", "enabled": "true"},
            {"id": "3", "name": "userB", "enabled": "true"},
        ]}
        with patch("week4.zap_context_builder._zap_api", return_value=valid):
            users = verify_imported_users("", "7", attestation)
        self.assertEqual([user["name"] for user in users], ["admin", "userA", "userB"])
        valid["usersList"][2]["enabled"] = "false"
        with patch("week4.zap_context_builder._zap_api", return_value=valid):
            with self.assertRaises(ZapContextError):
                verify_imported_users("", "7", attestation)


if __name__ == "__main__":
    unittest.main()
