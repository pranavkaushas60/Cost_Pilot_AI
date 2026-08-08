import importlib.util
import unittest
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


if __name__ == "__main__":
    unittest.main()
