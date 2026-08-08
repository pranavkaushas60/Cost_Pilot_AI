import importlib.util
import json
import unittest
from http import HTTPStatus
from pathlib import Path


FUNCTION_PATH = Path(__file__).resolve().parents[1] / "api" / "demo-requests.py"
SPEC = importlib.util.spec_from_file_location("demo_requests_function", FUNCTION_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VercelFunctionValidationTests(unittest.TestCase):
    def test_normalizes_valid_payload(self) -> None:
        result = MODULE.validate_payload(
            {
                "email": " Person@Example.com ",
                "company": " Example · FinOps ",
                "requestType": "DEMO",
                "createdAt": "2026-08-08T12:00:00Z",
            }
        )

        self.assertEqual(
            result,
            (
                "person@example.com",
                "Example · FinOps",
                "demo",
                "2026-08-08T12:00:00Z",
            ),
        )

    def test_rejects_invalid_request_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid request type"):
            MODULE.validate_payload(
                {"email": "person@example.com", "requestType": "unknown"}
            )

    def test_vrcel_handler_returns_json_error_for_invalid_payload(self) -> None:
        class FakeRequest:
            method = "POST"
            path = "/api/demo-requests"
            headers = {}
            body = b'{"email": "invalid", "company": "Example", "requestType": "demo"}'

        class FakeResponse:
            def __init__(self) -> None:
                self.status_code = None
                self.headers = {}
                self.text = None
                self.data = None

            def set_data(self, data: bytes) -> None:
                self.data = data

        response = FakeResponse()
        MODULE.handler(FakeRequest(), response)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = json.loads(response.data.decode("utf-8"))
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
