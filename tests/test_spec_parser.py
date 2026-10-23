import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "week2"))

from spec_parser import extract_endpoints


class SpecParserTests(unittest.TestCase):
    def test_merges_path_and_operation_parameters(self):
        spec = {
            "paths": {
                "/widgets/{widget_id}": {
                    "parameters": [{"name": "widget_id", "in": "path"}],
                    "get": {"operationId": "widgets.read", "responses": {"200": {}}},
                }
            }
        }
        endpoint = extract_endpoints(spec)[0]
        self.assertEqual(endpoint["path_params"], ["widget_id"])
        self.assertTrue(endpoint["is_bola_candidate"])
        self.assertTrue(endpoint["public_object_read"])

    def test_marks_createdb_as_forbidden(self):
        spec = {"paths": {"/createdb": {"get": {"responses": {"200": {}}}}}}
        endpoint = extract_endpoints(spec)[0]
        self.assertTrue(endpoint["forbidden"])
        self.assertIn("Never execute", endpoint["execution_note"])

    def test_marks_state_changing_operation_disabled(self):
        spec = {"paths": {"/things/{id}": {"delete": {"parameters": [{"name": "id", "in": "path"}]}}}}
        endpoint = extract_endpoints(spec)[0]
        self.assertTrue(endpoint["state_changing"])
        self.assertFalse(endpoint["is_bola_candidate"])


if __name__ == "__main__":
    unittest.main()
