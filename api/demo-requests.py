"""Vercel Function for persistent AI-VMP demo requests."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any

import psycopg
from psycopg.rows import dict_row


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


class handler(BaseHTTPRequestHandler):
    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        print("[demo-requests] POST received")
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_BODY_SIZE:
                raise ValueError("Invalid request body.")

            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("The request body must be a JSON object.")
            email, company, request_type, created_at = validate_payload(payload)

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
            self.send_json(
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
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            print(f"[demo-requests] persistence failed: {type(error).__name__}: {error}")
            self.send_json(
                {"error": "The request could not be saved. Please try again."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_GET(self) -> None:  # noqa: N802
        admin_key = os.environ.get("ADMIN_API_KEY", "")
        authorization = self.headers.get("Authorization", "")
        if not admin_key or authorization != f"Bearer {admin_key}":
            self.send_json({"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return

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

            self.send_json(
                [
                    {
                        "id": row["id"],
                        "email": row["email"],
                        "company": row["company"],
                        "requestType": row["request_type"],
                        "createdAt": row["created_at"],
                    }
                    for row in rows
                ]
            )
        except Exception as error:
            print(f"[demo-requests] list failed: {type(error).__name__}: {error}")
            self.send_json(
                {"error": "Requests could not be loaded."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
