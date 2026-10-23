import json
import tempfile
import unittest
from pathlib import Path

from vampi_authz_lab.zap_allowlist import ZapAllowlistError, approved_request_pairs, load_zap_allowlist


class ZapAllowlistTests(unittest.TestCase):
    def write_manifest(self, document):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        path = Path(temporary_directory.name) / "allowlist.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def baseline_manifest(self):
        return {
            "schema_version": 1,
            "assessment_id": "local-safe-zap",
            "target": "http://127.0.0.1:5000",
            "allowed_requests": [{"method": "GET", "path": "/books/v1/known-book"}],
            "prohibitions": ["/createdb", "POST", "PUT", "PATCH", "DELETE"],
        }

    def test_accepts_exact_local_get_fixture_manifest(self):
        manifest = load_zap_allowlist(self.write_manifest(self.baseline_manifest()))
        self.assertEqual(approved_request_pairs(manifest), {("GET", "/books/v1/known-book")})

    def test_rejects_reset_path_and_state_changing_method(self):
        for request in (
            {"method": "GET", "path": "/createdb"},
            {"method": "DELETE", "path": "/users/v1/disposable-user"},
        ):
            with self.subTest(request=request):
                document = self.baseline_manifest()
                document["allowed_requests"] = [request]
                with self.assertRaises(ZapAllowlistError):
                    load_zap_allowlist(self.write_manifest(document))

    def test_rejects_nonlocal_target_and_query_path(self):
        document = self.baseline_manifest()
        document["target"] = "http://127.0.0.1:5001"
        with self.assertRaises(ZapAllowlistError):
            load_zap_allowlist(self.write_manifest(document))

        document = self.baseline_manifest()
        document["allowed_requests"] = [{"method": "GET", "path": "/books/v1/known-book?enumerate=1"}]
        with self.assertRaises(ZapAllowlistError):
            load_zap_allowlist(self.write_manifest(document))

    def test_requires_explicit_state_change_prohibitions(self):
        document = self.baseline_manifest()
        document["prohibitions"] = ["/createdb", "POST"]
        with self.assertRaises(ZapAllowlistError):
            load_zap_allowlist(self.write_manifest(document))


if __name__ == "__main__":
    unittest.main()
