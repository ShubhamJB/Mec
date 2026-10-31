# Find Your Mechanic — Frontend UI Spec (MVP; early plan, partly outdated)
**Version 1.0 | React SPA | Consumes `/api/v1` of the FastAPI backend**

Derived from the SRS, ERD and API design in this folder. The backend is implemented; this spec defines the React UI that sits on it. Where this file and the API design disagree, the API design wins.

## 1. Stack (proposed defaults)
| Concern | Choice | Note |
|---|---|---|
| Build | Vite + React 18 + TypeScript | `frontend/` at repo root |
| Routing | React Router | Role-guarded route groups |
| Server state | TanStack Query | One query-key factory per resource |
| Forms | react-hook-form + zod | Zod schemas mirror backend limits (§9) |
| Map | MapLibre GL or Leaflet with OpenStreetMap tiles | No API key; must have a list alternative |
| Styling | CSS variables (design tokens) + Tailwind or CSS modules | Tokens come from the chosen design direction (§3) |
| API types | Generated from `/openapi.json` (`openapi-typescript`) | Backend serves it when `DEBUG=true` |
| Tests | Vitest + Testing Library; Playwright for the three core flows | |

Env: `VITE_API_BASE_URL=http://localhost:8000/api/v1`. CORS origins `http://localhost:5173` and `:3000` are already allowed by the backend.

## 2. Users and route groups
| Group | Roles | Routes |
|---|---|---|
| Public | Visitor, any | `/`, `/garages`, `/garages/:id`, `/login`, `/register`, `/verify-email` |
| Customer | CUSTOMER | `/account`, `/account/reviews`, `/notifications` |
| Owner | GARAGE_OWNER | `/owner/*` |
| Admin | ADMIN | `/admin/login`, `/admin/*` |

Guards: unauthenticated customer/owner routes -> `/login?next=`; unauthenticated admin routes (`/admin/*`) -> `/admin/login?next=`; wrong role -> 403 page; `EMAIL_NOT_VERIFIED` on login -> verify-email prompt with resend; `ACCOUNT_SUSPENDED` -> suspended screen (no appeal flow in MVP). Standard user login (`/login`) disallows admin sign-in and points to `/admin/login`; admin login (`/admin/login`) strictly rejects non-admin users.

## 3. Design approach (uses the `design-taste-frontend` skill)
The skill is installed at `.agents/skills/design-taste-frontend` and has two modes; this product needs both.

| Surface | Skill mode | Why |
|---|---|---|
| Landing `/`, garage discovery `/garages`, public garage profile `/garages/:id`, auth pages | **Page run** (`SKILL.md`) | Read and scrolled by visitors; needs identity |
| Customer account, owner dashboard, admin console, notifications | **App screens** (`references/app-screens.md`, `draw.mjs --app`) | Worked in daily; dense, quiet, data-first |

Process when building:
1. Inventory what belongs to this product (mechanic/garage world: workshop signage, service bays, tools, tyres, hours on the door, a phone number to call, the neighbourhood). Write the one-line idea before any styling.
2. Deal directions and pick one that carries that idea, per surface type:
   - `node .agents/skills/design-taste-frontend/scripts/draw.mjs --sector <sector> --brief "<one line>" --sections <roles> --options 3`
   - `node .agents/skills/design-taste-frontend/scripts/draw.mjs --app --kind <kind> --brief "<one line>" --keep palette,type --out .taste-skill/app`
3. Share one palette and typeface across public and app surfaces; the app style keeps the page's colour and type.
4. Export the chosen tokens to `frontend/src/styles/tokens.css` (CSS variables, light + dark). Components read only tokens.
5. After each screen: screenshot at 1440 / 768 / 390 px, run the skill's inspector (`inspect.mjs`, `inspect.mjs --app`), fix, look again.

Non-negotiables carried from the skill's app-screen rules: colour goes on data not chrome; KPIs are numbers not icon tiles; flat surfaces with 1px borders; right-aligned tabular figures; no zebra tables, no gradients/glows, no emoji, no placeholder data like "John Doe" or "Acme"; zero prints as zero, missing as a grey dash; the shell names the product; the most frequent job is one click away.

Sample data in mocks and tests must be believable and internally consistent (rating averages computed from the distribution shown).

## 4. Shared UX contracts
- **Auth tokens:** access token in memory; refresh token in `sessionStorage` (backend returns it in the JSON body; httpOnly-cookie hardening is a future enhancement). On 401 call `POST /auth/refresh` once, rotate, retry; on failure clear session and go to `/login`. Logout calls `POST /auth/logout` with the refresh token.
- **Errors:** every failure is `{error:{code,message,details,request_id}}`. Show `message`; map `code` for behaviour (`EMAIL_NOT_VERIFIED`, `ACCOUNT_SUSPENDED`, `RATE_LIMIT_EXCEEDED` -> "try again shortly", `VALIDATION_ERROR` -> field errors from `details.errors`). Show `request_id` in a "copy details" affordance on 500s.
- **Pagination:** `{items,page,limit,total_items,total_pages}`; page state lives in the URL query string.
- **Times:** API is UTC ISO 8601. Operating hours are garage-local wall-clock; always display with the garage's `timezone`. Never convert hours to the viewer's zone.
- **Optimistic concurrency:** registration edit and admin decision send `expected_version`; a 409 refetches and shows "this changed, review and retry".
- **States:** every list and detail defines loading (skeleton matching layout), empty (trade wording, keeps its frame), error (retry), and populated. Notifications and analytics events never block the page.
- **Accessibility:** map always has a list alternative; location denied -> manual location entry (address/coordinates); phone shown as `tel:` link; focus states visible; contrast >= 4.5:1.

## 5. Public screens
| Screen | Endpoints | Key behaviour |
|---|---|---|
| Landing `/` | `GET /garages/nearby` | Ask for browser location; capture origin once and keep it when the map pans. Search box, filter chips, up to 3 nearest markers, link to full list. Denied -> manual location entry. |
| Discovery `/garages` | `GET /garages`, `GET /services`, `GET /vehicle-types` | Map and list agree on filters. Search by name; multi-select services and vehicle types (ANY within group, AND between); Open Now; sort nearest / highest rated / most reviewed (nearest disabled without coordinates). 10 per page. Card: name, distance_km, rating + count, availability badge, phone `tel:`, cover photo. Unrated sorts last. |
| Garage profile `/garages/:id` | `GET /garages/{id}`, `/reviews`, `/photos`, `/availability`; `POST .../analytics/profile-view` | Fire profile-view once per mount, fire-and-forget (ignore 429). Call button is a `tel:` link that also fires `call-click` without waiting. Shows name, description, phone, address, map pin, rating + distribution, availability (OPEN / CLOSED / TEMPORARILY_UNAVAILABLE with message), services, vehicle types, 7-day hours in garage timezone, photo gallery (first = cover), paginated reviews with sort. Never show owner email or moderation internals. |
| Register `/register` | `POST /auth/register/customer`, `/register/owner` | Role chooser; name 2-100, password 8-128; success -> "check your email". |
| Verify email `/verify-email?token=` | `POST /auth/verify-email`, `/resend-verification` | Auto-submit token; resend has a generic confirmation (no enumeration). |
| Login `/login` | `POST /auth/login` | Standard login for Customer and Garage Owner. Redirect: customer -> `next` or `/`, owner -> `/owner`. Disallows ADMIN accounts with a notice linking to `/admin/login`. |

## 6. Customer screens
| Screen | Endpoints | Key behaviour |
|---|---|---|
| Write review (on profile) | `POST /garages/{id}/reviews` | Rating 1-5 required, comment optional <= 2000 (rating-only allowed). Hidden for own garage. 409 -> show existing review with edit. |
| My review actions | `PATCH`/`DELETE /reviews/{id}` | Edit rating/comment independently; empty comment clears; delete is soft. Admin-removed reviews are read-only. |
| Report review | `POST /reviews/{id}/reports` | Reason SPAM / ABUSIVE_CONTENT / FAKE_REVIEW / IRRELEVANT / OTHER + optional details; not on own review; 409 -> "already reported". |
| Account `/account` | `GET`/`PATCH /users/me`, `PATCH /users/me/password` | Name only editable; password change signs out all sessions -> redirect to login. |
| Notifications `/notifications` | `GET /notifications`, `/unread-count`, `PATCH .../{id}/read`, `/read-all`, `DELETE` | Header bell with unread count (poll every 60 s and on focus). Filter all / unread. Related entity link by `related_entity_type`. |

## 7. Owner screens (app-screen style)
Shell: left nav (Dashboard, Garage, Hours & availability, Services & vehicles, Photos, Staff, Reviews, Analytics, Registration), top bar with garage name + status, bell.

| Screen | Endpoints | Key behaviour |
|---|---|---|
| Registration wizard `/owner/registration` | `POST/GET/PUT/PATCH /owner/garage-registration`, `GET .../history`, catalogs, `POST /services/custom`, `/vehicle-types/custom` | Steps: basics, location pin (map click -> lat/lng), services, vehicle types, 7-day hours, photos (0-10). Phone E.164. No garage -> wizard; PENDING -> status view + edit (PATCH with `expected_version`); REJECTED -> show reason + resubmit (PUT); APPROVED -> read-only summary. History tab lists snapshots and decisions. |
| Dashboard `/owner` | `GET /owner/dashboard` | One question: how is my garage performing and is it visible? Status + availability first, then views, call clicks, average rating, review count as plain figures. One-click availability toggle. |
| Garage profile `/owner/garage` | `GET`/`PATCH /owner/garage`, `POST/GET /owner/garage/profile-change-requests` | Phone/description save immediately. Name/address/coordinates open a change request; show the pending request and that public data is unchanged until approved; only one pending allowed. |
| Hours & availability | `GET/PUT /owner/garage/operating-hours`, `GET/PATCH /owner/garage/availability` | Seven rows, each explicitly open/closed; closed -> no times; opening < closing; no overnight. Temporary-unavailable toggle with message <= 300 chars, no auto-expiry; shows derived status and local time. |
| Services & vehicle types | `POST/DELETE /owner/garage/services`, `/vehicle-types` | Cannot remove the last active item from an approved garage (409 message shown). Add custom entry inline. |
| Photos | `GET/POST /owner/garage/photos`, `PATCH .../reorder`, `DELETE .../{id}` | JPEG/PNG/WebP <= 5 MB, max 10; drag to reorder (first is cover); client-side pre-check but server is authority (413/415 handled). |
| Staff `/owner/staff` | `GET/POST/PATCH/DELETE /owner/staff`, `GET /owner/staff/{id}` | Owner-only private directory. Owner may run the garage alone; empty state invites adding staff without treating it as required. Add/edit/deactivate staff; inactive records remain visible in management history. No staff data on public/customer pages and no staff login in this first slice. |
| Reviews | `GET /owner/reviews` | Display name, rating, comment, date only. No reply (excluded from MVP). |
| Analytics | `GET /owner/analytics/engagement`, `/ratings`, `/summary` | Date range with group_by day (<= 90 d) / week / month (<= 365 d); views and call clicks over time; current vs previous equal period; rating distribution. Label call clicks as "call button taps", not calls. |

## 8. Admin screens (app-screen style)
Shell: left nav (Overview, Registrations, Profile changes, Garages, Users, Review reports, Audit log). Dense tables with filters in the URL.

| Screen | Endpoints | Key behaviour |
|---|---|---|
| Admin Login `/admin/login` | `POST /auth/login` | Dedicated admin authentication gateway. Strictly verifies `ADMIN` role. Non-admin logins are rejected. Redirects to `next` (within `/admin`) or `/admin`. Unauthenticated `/admin/*` routes redirect here. |
| Overview | `GET /admin/dashboard` | Pending counts first (registrations, reports), then totals. Each count links to its filtered queue. |
| Registrations | `GET /admin/garage-registrations` (+ `/{id}`), `PATCH /admin/garage-registrations/{id}` | Queue filtered by status; detail shows owner, hours, catalogs, photos, version. Approve / reject (reason required) sends `expected_version`; 409 -> reload with notice. No reversal. |
| Profile changes | `GET /admin/garage-profile-change-requests`, `PATCH .../{id}` | Side-by-side current vs proposed values. |
| Garages | `GET /admin/garages`, `PATCH .../{id}/moderation`, `DELETE /admin/garages/{id}` | Suspend (reason required) / restore; delete needs reason and confirmation; no restore. |
| Users | `GET /admin/users` (+ `/{id}`), `PATCH .../{id}/status` | Cannot act on self or other admins (controls hidden). Suspension reason. |
| Review reports | `GET /admin/review-reports` (+ `/{id}`), `PATCH .../{id}` | Report + review + garage together; dismiss or remove review, note required. |
| Audit log | `GET /admin/audit-logs` | Filter by admin, action type, date range; read-only, append-only. |

Destructive or irreversible actions (reject, suspend, delete garage, remove review) use an in-page confirm with the required reason field, never a browser `confirm()`.

## 9. Validation limits (mirror the backend)
- Name 2-100 (user), garage name 2-150, description <= 2000, address <= 500, phone E.164, custom service/vehicle-type name 2-100.
- Password 8-128; change requires current + confirmation, new must differ.
- Review rating 1-5 integer, comment <= 2000; availability message <= 300.
- Hours: 7 unique ISO weekdays (1 = Monday), closed => null times, open => both with opening < closing.
- Pagination limits: lists default 10-20; max 100 catalog, 50 reviews/notifications.
- Photos: <= 10 active, <= 5 MB, JPEG/PNG/WebP.
- Staff: name 2–100, phone E.164, optional role title <= 50; staff is optional and deletion means deactivation.

## 10. Suggested structure
```
frontend/
  src/
    api/          client (fetch wrapper, refresh/retry), generated types, per-resource hooks
    auth/         session store, guards, role redirects
    components/   ui primitives (tokens only), shell layouts, map, charts
    features/     discovery, garage-profile, reviews, owner/*, admin/*, notifications
    routes/       route tree
    styles/       tokens.css (from chosen direction), base.css
    lib/          formatters (distance, local time), zod schemas
```

## 11. Build order
1. Scaffold, tokens, API client with refresh, auth pages and guards.
2. Public discovery + garage profile (core value: find and call a garage).
3. Customer reviews, reports, account, notifications.
4. Owner registration wizard, dashboard, hours/availability, catalogs, photos, staff CRUD, analytics.
5. Admin queues and moderation.
6. Playwright for: register -> verify -> login; discovery -> profile -> call click; owner registration -> admin approval -> garage public.

## 12. Out of scope (per SRS)
Messaging, booking, payments, quotations, roadside assistance request workflow, owner review replies, appeals, multi-branch, advanced analytics. No admin catalog management UI (no backend endpoint yet).

## 13. Open decisions
- Final visual direction (picked via `draw.mjs` when building, see §3).
- Map library (MapLibre vs Leaflet) and geocoding for manual location entry (backend has none; needs a client-side or third-party service).
- Admin seed: no seeded admin exists yet, so admin screens cannot be exercised until one is created.
