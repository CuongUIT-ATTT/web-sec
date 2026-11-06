import unittest

from authz_lab.read_only.spec_parser import extract_endpoints


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

    def test_marks_debug_write_bola_and_mass_assignment_candidates(self):
        spec = {
            "paths": {
                "/users/v1/_debug": {"get": {"operationId": "api_views.users.debug", "responses": {"200": {}}}},
                "/users/v1/{username}/password": {
                    "put": {
                        "operationId": "api_views.users.update_password",
                        "parameters": [{"name": "username", "in": "path"}],
                        "requestBody": {},
                        "responses": {"204": {}},
                    }
                },
                "/users/v1/register": {
                    "post": {
                        "operationId": "api_views.users.register_user",
                        "requestBody": {},
                        "responses": {"200": {}},
                    }
                },
            }
        }
        by_path = {ep["path"]: ep for ep in extract_endpoints(spec)}
        self.assertTrue(by_path["/users/v1/_debug"]["is_excessive_data_exposure_candidate"])
        self.assertFalse(by_path["/users/v1/_debug"]["is_bfla_candidate"])
        self.assertTrue(by_path["/users/v1/{username}/password"]["is_write_bola_candidate"])
        self.assertTrue(by_path["/users/v1/register"]["is_mass_assignment_candidate"])


if __name__ == "__main__":
    unittest.main()
