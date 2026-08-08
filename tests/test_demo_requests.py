import tempfile
import unittest
from pathlib import Path

from ai_vmp import create_demo_request, list_demo_requests


class DemoRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.db"

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_create_and_list_request(self) -> None:
        created = create_demo_request(
            {
                "email": "Person@Example.com",
                "company": "Example · FinOps",
                "requestType": "demo",
                "createdAt": "2026-08-08T12:00:00Z",
            },
            self.database_path,
        )

        self.assertEqual(created["id"], 1)
        self.assertEqual(created["email"], "person@example.com")
        self.assertEqual(list_demo_requests(self.database_path), [created])

    def test_rejects_invalid_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid work email"):
            create_demo_request({"email": "not-an-email"}, self.database_path)


if __name__ == "__main__":
    unittest.main()
