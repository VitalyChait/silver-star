Silver Star Backend (MVP)

This is the MVP backend service for the Silver Star job board.

Stack
- FastAPI
- SQLAlchemy (SQLite by default; Postgres-ready)
- Pydantic v2
- Uvicorn

Quickstart
1) Create a virtualenv and install dependencies
   - python -m venv .venv
   - source .venv/bin/activate
   - pip install -r requirements.txt

2) Run the API
   - uvicorn app.main:app --reload --port 8000

3) Visit
   - http://localhost:8000/health
   - http://localhost:8000/docs

Environment
- DATABASE_URL (optional) — defaults to sqlite:///./data.db
- SECRET_KEY (optional) — used for JWT token signing (auto-generated if missing; change in prod)

Notes
- Tables auto-create on startup for MVP. Migrations (Alembic) can be added later.
- CORS allows localhost frontend during development.

Troubleshooting
- ImportError about email-validator: ensure you reinstalled deps after pulling latest (`pip install -r requirements.txt`).
