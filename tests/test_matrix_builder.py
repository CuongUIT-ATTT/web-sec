import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "week2"))

from matrix_builder import build_test_matrix


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


if __name__ == "__main__":
    unittest.main()
