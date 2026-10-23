import tempfile
import unittest
from pathlib import Path

from vampi_authz_lab.common import read_json, write_redacted_json


class CommonTests(unittest.TestCase):
    def test_writes_non_secret_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "artifact.json"
            write_redacted_json(destination, {"status": "ok", "items": [1, 2]})
            self.assertEqual(read_json(destination), {"status": "ok", "items": [1, 2]})

    def test_refuses_bearer_token_in_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "artifact.json"
            with self.assertRaises(RuntimeError):
                write_redacted_json(destination, {"authorization": "Bearer " + "abcdefgh" + "ijklmnop"})

    def test_refuses_jwt_shaped_value_in_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "artifact.json"
            token = "ey" + "Jheaderpayload"
            with self.assertRaises(RuntimeError):
                write_redacted_json(destination, {"token": token})

    def test_reports_invalid_json_without_echoing_contents(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "invalid.json"
            source.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid JSON"):
                read_json(source)


if __name__ == "__main__":
    unittest.main()
