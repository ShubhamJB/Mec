# Find Your Mechanic — Build Handoff (as of 31 October 2026)

Snapshot of what was built after the original SRS / ERD / API design, how to run it, the decisions behind it, and what is left. Read this before continuing the work. Where this file and the API design disagree, the API design wins.

## 1. Repos and git state
| Repo | Location | Branch | Remote |
|---|---|---|---|
| Backend + docs | `Mec/` (this repo) | `develop` | none configured here |
| Frontend | `Mec/frontend/` (its own git repo, ignored by this one via `.gitignore`) | `main` | `https://github.com/ShubhamJB/mec_frontend.git` |

- Backend commit `3e47351` holds notifications, rate limiting, seeding, Docker and the discovery fixes. **Uncommitted in this repo:** local photo storage (`storage_service.py`, `config.py`, `main.py`, `Dockerfile`, `.env.example`, `.gitignore`, `docker-compose.yml`, `tests/test_local_storage.py`), the `/garages` search-by-address change, `CLAUDE.md`, the frontend UI spec, this document, and the design-skill folders (`.agents/`, `.claude/`, `skills-lock.json`; decide whether to commit or ignore them).
- Frontend commit `550f475` was the first push. **About 39 files are uncommitted there:** owner photos / services / hours pages, themes, maps and routing, the 3D landing page, theme switcher and more.
- Working rule from the organisation settings: the assistant never commits; the owner reviews and runs `git commit` themselves. The assistant may stage files.

## 2. Run it
```bash
cd backend
docker compose up -d --build db api   # PostGIS and API (:8000); start web separately if needed
docker compose exec api python -m app.db.seed   # 500 garages/owners, 200 customers, optional staff, reviews, reports, analytics
```
- API docs: `http://localhost:8000/docs` (needs `DEBUG=true`). Health: `/health`.
- Frontend dev server (hot reload): `cd frontend && npm install && npm run dev` → `http://localhost:5173` (proxies `/api` to `:8000`).
- Backend tests: `cd backend && uv run --extra dev pytest` (50 passing; mostly unit-level).
- Frontend checks: `npx tsc -p tsconfig.json --noEmit` and `npx vite build`.
- Reset only the database by removing the Compose project's `pgdata` volume, then start the database/API and seed again. Avoid `docker compose down -v` if uploads should be preserved.
- Verification emails are stubbed. Find the link with `docker compose logs api | grep -A8 "STUB EMAIL"` (INFO logging was enabled for this).
- Photo uploads need `STORAGE_PROVIDER=local` (set in compose); files live in the `uploads` volume and are served at `/api/v1/media`.

**Accounts:** the seed creates `admin@seed.example.com`, `owner0001`…`owner0500` and `customer0001`…`customer0200` at `@seed.example.com`. All share one password that the seed prints once (set `SEED_PASSWORD` to choose it). `owner0003` has an approved garage with data. `demo.owner2@seed.example.com` is a verified owner with no garage, for demoing registration. Passwords are deliberately not recorded here.

## 3. Backend: what changed in this phase
Done earlier and still true: auth, users, garage registration, catalogs, owner garage management, discovery, public garage, reviews, owner analytics, admin APIs, the original 17 entities in the initial Alembic migration. Garage staff is added by the follow-up migration below.

Added or fixed in this phase:
- **Notifications** (`/notifications` endpoints + `notification_service`): in-app rows and best-effort email created from admin decisions, suspensions, new reviews, report events.
- **Rate limiting** (slowapi, in memory per process): default limit everywhere, `RATE_LIMIT_AUTH` on register/login/resend, `RATE_LIMIT_ANALYTICS` on view/click events. 429 uses the standard error envelope.
- **Error codes:** `EMAIL_NOT_VERIFIED` and `ACCOUNT_SUSPENDED` now appear as the envelope `code`.
- **Local photo storage provider** (the old stub returned fake URLs and saved nothing): saves to `UPLOAD_DIR`, extension taken from the verified image type, path traversal blocked, served by a `/api/v1/media` mount.
- **Dev seed script** `app/db/seed.py` (idempotent guard, refuses to run twice).
- **Discovery fixes found by the seed data:** geometry cast crashed four services; null rendering broke listing without coordinates; `highest_rated` crashed and `most_reviewed` sorted ascending; stable ordering added.
- **Admin registrations list:** sorted by latest activity (decision time if decided, else submission time) with an id tiebreaker; items carry `reviewed_at`.
- **Search:** `/garages?search=` matches garage name **or address**.
- Docker: Dockerfile (non-root, runs migrations on start), compose with `db`, `api`, `web`.
- **Garage staff CRUD:** optional, private roster owned by a garage owner. Owners may run solo; list/detail/create/update/deactivate routes are under `/owner/staff`. Staff are not separate login accounts and are never returned by public/customer APIs. Migration `a91f0d6c3b42` adds `garage_staff`; owner screen is `/owner/staff`.

## 4. Frontend: what exists
Stack: React 18, TypeScript (strict), Vite, React Router, Leaflet, Three.js (lazy). Details in `frontend/README.md`.

**Routes**
| Path | Access |
|---|---|
| `/` | Public 3D landing page |
| `/find`, `/garages`, `/garages/:id`, `/login`, `/register`, `/verify-email` | Public (`/find` is the location-based app home) |
| `/admin/login` | Public, rejects non-admins |
| `/notifications`, `/account` | Any signed-in user (`/account` is a placeholder) |
| `/owner`, `/owner/registration`, `/owner/hours`, `/owner/photos`, `/owner/services`, `/owner/staff` | Garage owners only |
| `/admin`, `/admin/registrations` | Administrators only |

- **Guards:** `RoleGuard` redirects a wrong-role user to their own home. The backend enforces the same roles (checked with real tokens: admin, owner, customer, anonymous).
- **Owner area:** dashboard (availability card in plain words, "Close for now" with an optional message), weekly schedule, photos (multi-upload, reorder, cover, remove), services and vehicles, plus private staff CRUD. The schedule, photos and services pages open read-only with an **Edit** button.
- **Maps and routes:** hexagon pins with ratings, OSRM driving routes with alternatives, location picker on the registration form, saved location per browser session.
- **Discovery page:** search bar at the top (name or area), filters, sort, map toggle.
- **Themes** (`src/styles/themes/`): `harbor` (default), `modern`, `sky`, `slate`, `cobalt`, `original`. Switch in the footer or with `?theme=`. All colours come from tokens, nothing is hard-coded. Large colour fields use `--field` / `--field-ink`.
- **3D landing page** (`src/features/landing3d/`): one fixed WebGL canvas, five scenes, a camera that flies between them on scroll. A bolt unscrews from a nut; a hex-plate city map with clickable pins and a route; a car drives into a garage (click the OPEN sign to close it); review bars with a checklist clipboard and an approval stamp; a map pin that drops when the call-to-action is hovered. No app UI appears on it by design. Nut and bolt colours are fixed (`fixedColors.ts`).
- **Error boundary** in `main.tsx` so a render crash shows a message instead of a blank page.

## 5. Decisions and why
- **Map tiles:** OpenStreetMap public tiles in natural colours. CARTO's free basemap began returning "API key required" watermark tiles, so it was removed. Themes can tint tiles via `--map-tile-filter` but all leave it at `none`.
- **Routing:** public OSRM demo server (no key, no traffic, fair-use limits).
- **Contrast:** every theme's text/background pairs were checked to WCAG AA by script. Where a brand colour failed as text, a darker derived tone is used for text and the original for non-text parts (for example the `harbor` accent).
- **Landing without the app UI:** so the app can change freely.
- **Reduced motion:** the 3D page snaps the camera and turns off pointer tilt.
- **Sample data:** everything on the landing page is labelled sample data; no invented traction, user or revenue figures.

## 6. Known issues and next steps (suggested order)
1. **`/garages` 5→10 km fallback ignores filters.** The list endpoint counts all garages within 5 km, not the ones matching search/service/vehicle filters, so a restrictive filter can return nothing instead of widening to 10 km. `/garages/nearby` does this correctly. Fix in `discovery_service.list_garages` (reuse the filtered query for the count). A test run showed 106 disagreements between the two endpoints.
2. **`POST /auth/verify-email` returns 200 slightly before the commit**, so a script that logs in within milliseconds can get 403 `EMAIL_NOT_VERIFIED`. Commit before responding.
3. **No database-backed integration tests** (no `conftest.py`); the seed data plus the Docker Postgres make this straightforward.
4. **Landing page on phones is not handled** (scenes are framed for desktop; a portrait camera boost exists but is untested).
5. **Placeholders to replace:** `CONTACT_EMAIL` in `landing3d/content.ts` (`hello@findyourmechanic.com`); all sample garages and review counts.
6. **Photos in `frontend/public/landing/`** are unused by the 3D landing page. They came from the owner with unknown licences and show third-party brands; confirm rights before using them publicly.
7. **Owner pages not built:** garage profile (name/address change requests), reviews, analytics charts. **Customer side:** review edit/report UI, account page. Backend endpoints for all of these exist.
8. **Production readiness:** keyed or self-hosted tile and routing providers, S3-style storage with deletion retry, email outbox, structured logging (`structlog` unused), distributed rate limiting, anonymous analytics dedup.
9. **Docker:** rebuild the `web` image to pick up the latest frontend and the 6 MB upload limit in `nginx.conf.template`.
10. **Docs:** `Find_Your_Mechanic_Frontend_UI_Spec.md` was written before most of the above; its route table, theme and landing sections are out of date. Prefer `frontend/README.md` and this file.
11. **Roadside assistance:** a technical plan is documented in the API design, but no roadside feature is implemented. First decide coverage/radius, explicit opt-in and availability, response/expiry expectations, cancellation, pricing, sensitive location/contact handling, safety and support boundaries. The proposed MVP is one customer request to one eligible garage; owner accepts or declines, then calls to confirm problem, price and ETA. Precise location/contact stays private until acceptance. Use dedicated request/capability/event tables, owner-scoped transitions, an outbox for notification retries, and polling plus delivery fallback. Garage staff are not request actors in the initial slice.

## 7. Working conventions
- No new code comments unless asked (project rule in the user's global instructions); prefer descriptive names.
- Never commit automatically; never store or echo real secrets; seed passwords are for local data only.
- Staff roster and staff CRUD are owner-private. Do not add staff data to public APIs or expose it to customers. Zero staff is a valid garage state; deactivation preserves history.
- Frontend design work uses the installed `design-taste-frontend` skill (`.agents/skills/`). Its generated working files go to `.taste-skill/` (ignored). The owner usually reviews UI visually themselves.
- `CLAUDE.md` at the repo root has the backend architecture and conventions.
