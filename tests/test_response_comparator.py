import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "week2"))

from response_comparator import analyze_all, json_similarity, normalize_json


class ResponseComparatorTests(unittest.TestCase):
    def test_normalizes_dynamic_fields_recursively(self):
        value = {"timestamp": "now", "outer": {"request_id": "x", "secret": "value"}}
        self.assertEqual(normalize_json(value), {"outer": {"secret": "value"}})

    def test_similarity_for_equal_nested_json(self):
        left = {"book": {"secret": "fixture", "owner": "userA"}}
        right = {"book": {"owner": "userA", "secret": "fixture"}}
        self.assertEqual(json_similarity(left, right), 1.0)

    def test_confirms_cross_user_secret_exposure(self):
        fixture = {"resource_id": "userA-book"}
        baseline = {
            "operation_id": "get-book",
            "fixture": fixture,
            "scenario": "owner_control",
            "risk_category": "BOLA",
            "status_code": 200,
            "response_json": {"book_title": "userA-book", "secret": "fixture", "owner": "userA"},
        }
        cross_user = {
            "operation_id": "get-book",
            "fixture": fixture,
            "scenario": "cross_user",
            "risk_category": "BOLA",
            "status_code": 200,
            "response_json": {"book_title": "userA-book", "secret": "fixture", "owner": "userA"},
        }
        final = analyze_all([baseline, cross_user])
        self.assertEqual(final[0]["verdict"], "CONTROL_PASS")
        self.assertEqual(final[1]["verdict"], "CONFIRMED")
        self.assertEqual(final[1]["evidence_paths"], ["$.secret"])

    def test_marks_public_read_as_observation(self):
        result = {
            "risk_category": "PUBLIC_OBJECT_READ",
            "scenario": "anonymous_observation",
            "status_code": 200,
            "response_json": {"username": "userA"},
        }
        self.assertEqual(analyze_all([result])[0]["verdict"], "OBSERVATION")

    def test_confirms_debug_endpoint_credential_exposure(self):
        anon_debug = {
            "operation_id": "api_views.users.debug",
            "risk_category": "EXCESSIVE_DATA_EXPOSURE",
            "scenario": "anonymous",
            "status_code": 200,
            "response_json": {"users": [{"username": "admin", "password": "secret-password", "admin": True}]},
        }
        analyzed = analyze_all([anon_debug])[0]
        self.assertEqual(analyzed["verdict"], "CONFIRMED")
        self.assertEqual(analyzed["evidence_paths"], ["$.users[*].password"])
        self.assertEqual(
            analyzed["response_json"],
            {"user_record_count": 1, "exposed_field_names": ["admin", "password", "username"]},
        )
        self.assertNotIn("secret-password", str(analyzed))


if __name__ == "__main__":
    unittest.main()
