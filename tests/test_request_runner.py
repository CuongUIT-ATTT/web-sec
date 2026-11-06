import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "week2"))

from request_runner import SafetyError, _response_record, concrete_url, send_read_request, validate_base_url


class RequestRunnerTests(unittest.TestCase):
    def test_allows_exact_local_origin(self):
        self.assertEqual(validate_base_url("http://127.0.0.1:5000"), "http://127.0.0.1:5000")
        self.assertEqual(concrete_url("http://127.0.0.1:5000", "/books/v1/a b"), "http://127.0.0.1:5000/books/v1/a%20b")

    def test_rejects_non_loopback_origin(self):
        for base_url in ("http://localhost:5000", "https://127.0.0.1:5000", "http://127.0.0.1:5001"):
            with self.subTest(base_url=base_url):
                with self.assertRaises(SafetyError):
                    validate_base_url(base_url)

    def test_blocks_state_change_before_network_request(self):
        with self.assertRaises(SafetyError):
            send_read_request("PUT", "/users/v1/userA/password", "http://127.0.0.1:5000")

    def test_blocks_database_reset_before_network_request(self):
        with self.assertRaises(SafetyError):
            send_read_request("GET", "/createdb", "http://127.0.0.1:5000")

    def test_debug_endpoint_records_only_count_and_field_names_without_passwords(self):
        raw_body = b'{"users": [{"username": "admin", "password": "pass1-StrongPass", "email": "a@b.c", "admin": true}]}'
        record = _response_record(200, {"Content-Type": "application/json"}, raw_body, endpoint="/users/v1/_debug")
        self.assertEqual(
            record["response_json"],
            {"user_record_count": 1, "exposed_field_names": ["admin", "email", "password", "username"]},
        )
        self.assertIsNone(record["response_text"])
        self.assertNotIn("StrongPass", str(record))
        self.assertNotIn("pass1", str(record))


if __name__ == "__main__":
    unittest.main()
