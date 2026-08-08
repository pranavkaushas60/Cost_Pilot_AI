# AI-VMP

AI-VMP is a lightweight landing page and demo-request backend for an AI vendor
management platform. It combines a polished marketing website with a small Python
API that stores demo enquiries in a local SQLite database.

## Features

- Responsive landing page for product positioning and pricing
- Book-a-demo modal with email and company capture
- SQLite-backed demo request storage
- JSON API for creating and listing requests
- Input validation and parameterized database queries
- Simple local development workflow with Python and uv

## Project structure

```text
.
├── api/                        # Vercel-compatible demo request function
├── data/                       # Local SQLite database (ignored by Git)
├── src/ai_vmp/                 # Application source code
│   ├── api/                    # API package
│   ├── core/                   # Shared infrastructure
│   ├── services/               # Service layer
│   ├── static/                 # CSS, JavaScript, and images
│   ├── templates/              # Templates
│   └── __init__.py             # HTTP server and DB implementation
├── tests/                      # Automated tests
├── index.html                  # Website frontend
├── pyproject.toml              # Python project configuration
└── uv.lock                     # Dependency lockfile
```

## Requirements

- Python 3.12 or newer
- uv

## Run locally

Install dependencies:

```bash
uv sync
```

Start the local server:

```bash
uv run ai-vmp
```

Open http://127.0.0.1:8000 in your browser.

The app will create the local database automatically at data/demo_requests.db.

## API

### Create a demo request

```http
POST /api/demo-requests
Content-Type: application/json
```

Example payload:

```json
{
  "email": "person@example.com",
  "company": "Example Company · FinOps Lead",
  "requestType": "demo",
  "createdAt": "2026-08-08T12:00:00Z"
}
```

### List demo requests

```http
GET /api/demo-requests
```

## Run tests

```bash
uv run python -m unittest discover -s tests -v
```

## Notes

- Local development uses SQLite.
- Production deployment can use a PostgreSQL-backed setup.
- Do not commit database credentials, environment files, or the local SQLite DB.

## License

No license has been selected yet. All rights are reserved by the project owner.
