"""AI-VMP local website and demo-request API."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_FILE = PROJECT_ROOT / "index.html"
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "demo_requests.db"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ALLOWED_REQUEST_TYPES = {
    "access",
    "assessment",
    "demo",
    "enterprise",
    "platform",
    "pricing",
}


def connect_database(database_path: Path = DEFAULT_DATABASE) -> sqlite3.Connection:
    """Open the SQLite database and create its schema when needed."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            company TEXT NOT NULL DEFAULT '',
            request_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def create_demo_request(payload: dict[str, Any], database_path: Path) -> dict[str, Any]:
    """Validate and persist one demo request."""
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

    with connect_database(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO demo_requests (email, company, request_type, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (email, company, request_type, created_at),
        )
        request_id = cursor.lastrowid

    return {
        "id": request_id,
        "email": email,
        "company": company,
        "requestType": request_type,
        "createdAt": created_at,
    }


def list_demo_requests(database_path: Path) -> list[dict[str, Any]]:
    """Return all demo requests in insertion order."""
    with connect_database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, email, company, request_type, created_at
            FROM demo_requests
            ORDER BY id ASC
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "email": row["email"],
            "company": row["company"],
            "requestType": row["request_type"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def make_handler(database_path: Path, index_file: Path = INDEX_FILE) -> type[BaseHTTPRequestHandler]:
    """Create an HTTP handler bound to the requested files."""

    class WebsiteHandler(BaseHTTPRequestHandler):
        def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/demo-requests":
                self.send_json(list_demo_requests(database_path))
                return
            if path in {"/", "/index.html"}:
                if not index_file.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND, "index.html was not found")
                    return
                body = index_file.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/demo-requests":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > 16_384:
                    raise ValueError("Invalid request body.")
                payload = json.loads(self.rfile.read(content_length))
                if not isinstance(payload, dict):
                    raise ValueError("The request body must be a JSON object.")
                entry = create_demo_request(payload, database_path)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json(entry, HTTPStatus.CREATED)

    return WebsiteHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI-VMP website locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()

    connect_database(args.database).close()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.database))
    print(f"AI-VMP is running at http://{args.host}:{args.port}")
    print(f"Demo requests database: {args.database.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AI-VMP.")
    finally:
        server.server_close()


__all__ = ["create_demo_request", "list_demo_requests", "main"]
