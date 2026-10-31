# Find Your Mechanic

Location-based garage discovery platform (MVP). Customers find nearby garages, call them, and review them. Owners register one garage subject to admin approval. Admins moderate.

Personal practice/side project. Backend is the active codebase; no frontend in this repo yet (planned: React).

## Repo layout
- `Find_Your_Mechanic_MVP_Handoff/` — source of truth for requirements: `SRS_MVP.md`, `ERD_Data_Model.md`, `API_Design.md`, `find_your_mechanic_erd.mmd`. The `.docx` files mirror the `.md` files.
- `Find_Your_Mechanic_MVP_Handoff/Find_Your_Mechanic_Frontend_UI_Spec.md` — React UI spec (routes, endpoint mapping, design process). Frontend work uses the `design-taste-frontend` skill installed in `.agents/skills/`.
- `backend/` — FastAPI service (Python >= 3.14, managed with `uv`).

Read the relevant handoff `.md` before implementing or changing behavior; the API design lists the exact rules, status codes, and DTOs per endpoint.

## Backend stack
FastAPI, async SQLAlchemy 2 + asyncpg, Alembic (psycopg2 for migrations), PostgreSQL + PostGIS (GeoAlchemy2), Pydantic v2 / pydantic-settings, python-jose (JWT), passlib/bcrypt, Pillow, timezonefinder, aiosmtplib. Dev: pytest, ruff, mypy (strict).

## Commands (run from `backend/`)
- Install: `uv sync --extra dev`
- Run: `uv run uvicorn app.main:app --reload` (docs at `/docs` when `DEBUG=true`)
- Migrate: `uv run alembic upgrade head`; new migration: `uv run alembic revision --autogenerate -m "..."`
- Seed dev data (500 garages, 500 owners, 200 customers, optional garage staff, reviews, reports, analytics; database/API containers must be up): `docker compose exec api python -m app.db.seed`. Includes a solo-owner garage and a multi-staff garage. Admin is `admin@seed.example.com`; all seeded accounts share one password, printed once at the end (set `SEED_PASSWORD` to choose it). Refuses to run twice. Reset only the database by removing the Compose project's `pgdata` volume; avoid `docker compose down -v` if uploads should be preserved.
- Test: `uv run pytest`
- Lint/types: `uv run ruff check .`, `uv run mypy app`
- Config: copy `.env.example` to `.env`. Never commit secrets.

`backend/main.py` is an unused placeholder; the app entry point is `app/main.py` (`create_app()`).

## Architecture
Layered: `api/v1/endpoints` (thin routes) -> `services` (business logic, DB access) -> `models` (SQLAlchemy) with `schemas` (Pydantic DTOs) at the boundary.

- `app/main.py` — app factory, CORS, `X-Request-ID` middleware, error handlers, `/health`.
- `app/api/v1/router.py` — mounts all routers under `/api/v1`. Several endpoint modules expose multiple routers (e.g. `services_router`, `owner_services_router`, `public_garage_services_router`) because one resource is served under public and `/owner` prefixes.
- `app/core/` — `config.py` (settings), `deps.py` (auth dependencies: `get_current_user`, `get_optional_user`, `require_customer|owner|admin`), `jwt.py`, `security.py` (hashing), `errors.py` (error envelope), `pagination.py`.
- `app/db/session.py` — `get_db` commits on success and rolls back on exception, so services call `flush()`, not `commit()`.
- `app/utils/` — `availability.py` (derived OPEN/CLOSED/TEMPORARILY_UNAVAILABLE), `geo.py`, `email.py` (logs to console when SMTP unconfigured).
- `app/services/storage_service.py` — storage provider interface. `stub` returns fake URLs and saves nothing; `local` (`STORAGE_PROVIDER=local`, used in docker-compose) saves to `UPLOAD_DIR` and is served at `/api/v1/media`. S3/GCS/Cloudinary are not implemented.

## Conventions
- Error envelope: `{"error": {"code", "message", "details", "request_id"}}`; code is derived from HTTP status in `core/errors.py`. Raise `HTTPException`; don't hand-build error responses.
- Identity and garage ownership always come from the JWT, never from client-supplied IDs.
- Public garage eligibility: approved AND not suspended AND not deleted AND owner ACTIVE. Reuse the shared helpers (e.g. `verify_public_garage`, discovery query logic) instead of re-implementing this.
- Soft delete (`deleted_at`) for users, garages, reviews, photos. Always filter on it.
- Timestamps are UTC; operating hours are local wall-clock in the garage's IANA timezone (derived from coordinates).
- Admin state-changing actions must write an audit row via `record_admin_action`.
- Optimistic concurrency on registration decisions via `expected_version`; stale decisions return 409.
- Tests are currently unit tests over schemas/utilities (no DB or `conftest.py` yet).

## Implementation status
Done (matches API design): auth, users, garage registration, services and vehicle-type catalogs, owner garage profile/hours/availability/photos/change requests, discovery (`/garages/nearby`, `/garages`), public garage + analytics events, reviews + reports, owner dashboard/analytics, admin APIs, notifications (`/notifications` endpoints; in-app rows plus best-effort email created from admin decisions, suspensions, new reviews, and report events via `notification_service.notify_user`/`notify_admins`), rate limiting (slowapi: default limit on all routes, `RATE_LIMIT_AUTH` on register/login/resend-verification, `RATE_LIMIT_ANALYTICS` on view/click events), specific `EMAIL_NOT_VERIFIED`/`ACCOUNT_SUSPENDED` error codes (see `SPECIFIC_ERROR_MESSAGES` in `core/errors.py`), initial Alembic migration (all 17 entities).

Remaining / gaps:
- **Photo storage** — local disk only; no S3/GCS/Cloudinary provider, and cloud deletion failures are logged but never retried.
- **Structured logging** — `structlog` is a dependency but unused.
- **Analytics dedup** — only a 15-minute debounce for authenticated users; anonymous views are not deduplicated.
- **Tests** — no integration/API tests against a database; no `conftest.py`.
- **Email** — sent inline and best-effort; no outbox/retry.
- **Housekeeping** — empty `backend/README.md`; unused `backend/main.py`; leftover "Future modules" comment in `router.py`.
