import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "week2"))

from matrix_builder import build_test_matrix, filter_fixtures_for_roles


class MatrixBuilderTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = [
            {
                "resource_type": "book",
                "resource_id": "userA-book",
                "owner_role": "userA",
                "owner_username": "userA",
                "path_template": "/books/v1/{book_title}",
            }
        ]
        self.endpoint = {
            "operation_id": "api_views.books.get_by_title",
            "path": "/books/v1/{book_title}",
            "method": "GET",
            "path_params": ["book_title"],
            "requires_auth": True,
            "is_bola_candidate": True,
            "public_object_read": False,
            "forbidden": False,
        }

    def test_generates_only_known_fixture_paths(self):
        cases = build_test_matrix([self.endpoint], self.fixtures, ["admin", "userA", "userB"])
        self.assertEqual(len(cases), 5)
        self.assertEqual({case["endpoint"] for case in cases}, {"/books/v1/userA-book"})
        self.assertEqual(sum(case["scenario"] == "owner_control" for case in cases), 1)
        self.assertEqual(sum(case["scenario"] == "cross_user" for case in cases), 2)

    def test_does_not_match_different_template(self):
        endpoint = {**self.endpoint, "path": "/users/v1/{username}", "path_params": ["username"]}
        self.assertEqual(build_test_matrix([endpoint], self.fixtures, ["userA"]), [])

    def test_generates_readonly_excessive_exposure_debug_cases(self):
        debug_endpoint = {
            "operation_id": "api_views.users.debug",
            "path": "/users/v1/_debug",
            "method": "GET",
            "path_params": [],
            "requires_auth": False,
            "is_bola_candidate": False,
            "is_bfla_candidate": False,
            "is_excessive_data_exposure_candidate": True,
            "public_object_read": False,
            "forbidden": False,
        }
        cases = build_test_matrix([debug_endpoint], self.fixtures, ["admin", "userA"])
        self.assertEqual(len(cases), 3)
        self.assertEqual({c["risk_category"] for c in cases}, {"EXCESSIVE_DATA_EXPOSURE"})
        self.assertEqual({c["scenario"] for c in cases}, {"anonymous", "admin_control", "unprivileged_role"})

    def test_automatically_filters_fixtures_to_configured_roles_subset(self):
        five_role_fixtures = [
            {"resource_type": "book", "resource_id": "userA-book", "owner_role": "userA", "owner_username": "userA", "path_template": "/books/v1/{book_title}"},
            {"resource_type": "book", "resource_id": "userB-book", "owner_role": "userB", "owner_username": "userB", "path_template": "/books/v1/{book_title}"},
            {"resource_type": "book", "resource_id": "admin2-book", "owner_role": "admin2", "owner_username": "admin2", "path_template": "/books/v1/{book_title}"},
            {"resource_type": "user_profile", "resource_id": "userA", "owner_role": "userA", "owner_username": "userA", "path_template": "/users/v1/{username}"},
            {"resource_type": "user_profile", "resource_id": "userC", "owner_role": "userC", "owner_username": "userC", "path_template": "/users/v1/{username}"},
        ]
        profile_endpoint = {
            "operation_id": "api_views.users.get_by_username",
            "path": "/users/v1/{username}",
            "method": "GET",
            "path_params": ["username"],
            "requires_auth": False,
            "is_bola_candidate": False,
            "public_object_read": True,
            "forbidden": False,
        }
        filtered = filter_fixtures_for_roles(five_role_fixtures, ["admin", "userA", "userB"])
        self.assertEqual([f["resource_id"] for f in filtered], ["userA-book", "userB-book", "userA"])

        cases = build_test_matrix([self.endpoint, profile_endpoint], five_role_fixtures, ["admin", "userA", "userB"])
        endpoints_tested = {c["endpoint"] for c in cases}
        self.assertIn("/books/v1/userA-book", endpoints_tested)
        self.assertIn("/books/v1/userB-book", endpoints_tested)
        self.assertIn("/users/v1/userA", endpoints_tested)
        self.assertNotIn("/books/v1/admin2-book", endpoints_tested)
        self.assertNotIn("/users/v1/userC", endpoints_tested)


if __name__ == "__main__":
    unittest.main()
