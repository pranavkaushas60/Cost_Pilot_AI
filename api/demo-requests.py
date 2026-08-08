"""Vercel Function for persistent AI-VMP demo requests."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - allows local tests without the dependency
    psycopg = None
    dict_row = None


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ALLOWED_REQUEST_TYPES = {
    "access",
    "assessment",
    "demo",
    "enterprise",
    "platform",
    "pricing",
}
MAX_BODY_SIZE = 16_384


def validate_payload(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    email = str(payload.get("email", "")).strip().lower()
    company = str(payload.get("company", "")).strip()
    request_type = str(payload.get("requestType", "demo")).strip().lower()
    created_at = str(payload.get("createdAt", "")).strip() or datetime.now(UTC).isoformat()

    if not EMAIL_PATTERN.fullmatch(email) or len(email) > 254:
        raise ValueError("Enter a valid work email address.")
    if len(company) > 200:
        raise ValueError("Company and role must be 200 characters or fewer.")
    if request_type not in ALLOWED_REQUEST_TYPES:
        raise ValueError("Invalid request type.")

    return email, company, request_type, created_at


def get_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return database_url


def _get_request_body(request: Any) -> bytes:
    body = getattr(request, "body", None)
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    if hasattr(request, "data") and isinstance(request.data, (bytes, bytearray)):
        return bytes(request.data)
    if hasattr(request, "get_data"):
        return request.get_data()
    return b""


def _get_request_headers(request: Any) -> dict[str, str]:
    headers = getattr(request, "headers", {}) or {}
    if isinstance(headers, dict):
        return {str(key): str(value) for key, value in headers.items()}
    return {str(key): str(value) for key, value in dict(headers).items()}


def _send_json(response: Any, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload, default=str).encode("utf-8")
    response.status_code = status
    response.headers = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}
    response.text = body.decode("utf-8")
    response.data = body


def handler(request: Any, response: Any) -> Any:
    print("[demo-requests] request received")
    method = getattr(request, "method", "")
    path = getattr(request, "path", "")

    if method == "GET":
        admin_key = os.environ.get("ADMIN_API_KEY", "")
        authorization = _get_request_headers(request).get("Authorization", "")
        if not admin_key or authorization != f"Bearer {admin_key}":
            _send_json(response, {"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return response

        if psycopg is None or dict_row is None:
            _send_json(response, {"error": "Database support is unavailable"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return response

        try:
            with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, email, company, request_type, created_at
                        FROM demo_requests
                        ORDER BY created_at DESC
                        LIMIT 500
                        """
                    )
                    rows = cursor.fetchall()

            _send_json(
                response,
                [
                    {
                        "id": row["id"],
                        "email": row["email"],
                        "company": row["company"],
                        "requestType": row["request_type"],
                        "createdAt": row["created_at"],
                    }
                    for row in rows
                ],
            )
        except Exception as error:
            print(f"[demo-requests] list failed: {type(error).__name__}: {error}")
            _send_json(response, {"error": "Requests could not be loaded."}, HTTPStatus.INTERNAL_SERVER_ERROR)
        return response

    if method != "POST" or path != "/api/demo-requests":
        _send_json(response, {"error": "Not Found"}, HTTPStatus.NOT_FOUND)
        return response

    print("[demo-requests] POST received")
    try:
        body = _get_request_body(request)
        if not body or len(body) > MAX_BODY_SIZE:
            raise ValueError("Invalid request body.")

        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("The request body must be a JSON object.")
        email, company, request_type, created_at = validate_payload(payload)

        if psycopg is None or dict_row is None:
            raise RuntimeError("Database support is unavailable")

        with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO demo_requests
                        (email, company, request_type, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, email, company, request_type, created_at
                    """,
                    (email, company, request_type, created_at),
                )
                row = cursor.fetchone()

        assert row is not None
        print(f"[demo-requests] saved id={row['id']}")
        _send_json(
            response,
            {
                "id": row["id"],
                "email": row["email"],
                "company": row["company"],
                "requestType": row["request_type"],
                "createdAt": row["created_at"],
            },
            HTTPStatus.CREATED,
        )
    except (ValueError, json.JSONDecodeError) as error:
        print(f"[demo-requests] validation failed: {error}")
        _send_json(response, {"error": str(error)}, HTTPStatus.BAD_REQUEST)
    except Exception as error:
        print(f"[demo-requests] persistence failed: {type(error).__name__}: {error}")
        _send_json(response, {"error": "The request could not be saved. Please try again."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    return response
