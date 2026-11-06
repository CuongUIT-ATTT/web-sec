import unittest

from authz_lab.verification.manual_verifier import (
    VerificationSafetyError,
    _access_direction,
    _is_admin_role,
    _owner_baseline_is_valid,
    _url_for_path,
)


class ManualVerifierTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "resource_type": "book",
            "resource_id": "known-book",
            "owner_role": "userA",
            "owner_username": "userA",
            "path_template": "/books/v1/{book_title}",
        }

    def test_validates_owner_response_shape(self):
        response = {
            "status_code": 200,
            "response_json": {"book_title": "known-book", "owner": "userA", "secret": "fixture secret"},
        }
        self.assertTrue(_owner_baseline_is_valid(response, self.fixture))
        self.assertFalse(_owner_baseline_is_valid({**response, "response_json": {"owner": "userA"}}, self.fixture))

    def test_rejects_nonlocal_targets_and_queries(self):
        with self.assertRaises(VerificationSafetyError):
            _url_for_path("http://localhost:5000", "/books/v1/known-book")
        with self.assertRaises(VerificationSafetyError):
            _url_for_path("http://127.0.0.1:5000", "/books/v1/known-book?scan=yes")

    def test_escapes_fixture_path_segments(self):
        url = _url_for_path("http://127.0.0.1:5000", "/books/v1/space title")
        self.assertEqual(url, "http://127.0.0.1:5000/books/v1/space%20title")

    def test_multi_role_admin_detection_and_four_directions(self):
        self.assertTrue(_is_admin_role("admin"))
        self.assertTrue(_is_admin_role("admin2"))
        self.assertTrue(_is_admin_role("custom_op", {"is_admin": True}))
        self.assertFalse(_is_admin_role("userA"))
        self.assertEqual(_access_direction(False, False), "USER_TO_USER")
        self.assertEqual(_access_direction(False, True), "USER_TO_ADMIN")
        self.assertEqual(_access_direction(True, False), "ADMIN_TO_USER")
        self.assertEqual(_access_direction(True, True), "ADMIN_TO_ADMIN")


if __name__ == "__main__":
    unittest.main()
