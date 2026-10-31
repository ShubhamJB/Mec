# Find Your Mechanic — REST API Design (MVP)
**Version 1.0 | Base path `/api/v1` | 30 October 2026**

## 1. API conventions
- JSON except photo upload (`multipart/form-data`).
- Bearer JWT access token. Refresh token rotation; store only token hash.
- Roles: `CUSTOMER`, `GARAGE_OWNER`, `ADMIN`; derive identity from JWT.
- Timestamps are ISO 8601 UTC. Operating-hour times are local to garage IANA timezone.
- Pagination: `page` starts at 1; include `{page,limit,total_items,total_pages}`.
- Error envelope: `{"error":{"code":"...","message":"...","details":{},"request_id":"..."}}`.
- Common codes: 400 malformed/invalid token, 401 unauthenticated, 403 forbidden, 404 missing/not publicly visible, 409 conflict, 413 too large, 415 unsupported media, 422 validation, 429 rate limit, 500 unexpected.

## 2. Authentication — `/auth`
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| POST `/auth/register/customer` | Public | `full_name,email,password` | Backend assigns CUSTOMER; normalize unique email; name 2–100; password 8–128; send verification. 201/409/422. |
| POST `/auth/register/owner` | Public | Same | Backend assigns GARAGE_OWNER. 201/409/422. |
| POST `/auth/login` | Public | `email,password` | Require verified email and ACTIVE account. Shared across roles. 200; 401 invalid credentials; 403 EMAIL_NOT_VERIFIED/ACCOUNT_SUSPENDED. |
| POST `/auth/refresh` | Refresh token | `refresh_token` | Validate type/signature/expiry/revocation; rotate; store hash and revoke old. 200/401/403. |
| POST `/auth/logout` | Authenticated | Current refresh session | Revoke current refresh session. 200/401. |
| POST `/auth/logout-all` | Authenticated | None | Revoke all refresh sessions. 200/401. |
| POST `/auth/verify-email` | Public | `token` | Hash lookup, expiry/used/revoked checks; mark verified and token used. 200/400/404/422. |
| POST `/auth/resend-verification` | Public | `email` | Rate-limited generic response to avoid enumeration. 200/422/429. |

Register response: `{message,user:{id,full_name,email,role}}`. Token response: `{access_token,refresh_token,token_type,expires_in}`. Unverified users cannot log in.

## 3. Customer profile — `/users`
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/users/me` | Authenticated | — | Own profile: id, name, email, role, account_status, created_at. 200/401. |
| PATCH `/users/me` | Authenticated | `full_name` | Name only, 2–100; reject empty patch and role/status changes. 200/401/422. |
| PATCH `/users/me/password` | Authenticated | `current_password,new_password,confirm_password` | Verify current; new 8–128, different; confirmation matches; revoke all refresh sessions. 200/400/401/422. |

## 4. Garage registration — `/owner/garage-registration`
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| POST `/owner/garage-registration` | Verified owner | name, description, phone, address, latitude, longitude, service_ids, optional custom_services, vehicle_type_ids, optional custom_vehicle_types, 7 operating_hours, optional 0–10 photos | One non-deleted garage/owner; name 2–150; description max 2000; phone E.164; address max 500; valid coordinates; at least one active service/type; exactly 7 unique ISO weekdays; closed day has null times; open day has both times and opening<closing; derive timezone; transactionally create garage/history snapshot/hours. 201/401/403/409/422. |
| GET `/owner/garage-registration` | Owner | — | Current registration status and latest decision. 200/401/403/404. |
| GET `/owner/garage-registration/history` | Owner | — | All submission snapshots/decisions. 200/401/403/404. |
| PUT `/owner/garage-registration` | Owner | Full registration DTO | Only REJECTED; update same garage, create new history snapshot, set PENDING and increment version. 200/401/403/404/409/422. |
| PATCH `/owner/garage-registration` | Owner | Partial editable fields + `expected_version` | Only PENDING; update current record, increment version; original snapshot unchanged. 200/401/403/404/409/422. |

Suggested DTOs:
- Registration: `{name,description,phone,address,latitude,longitude,service_ids[],custom_services[],vehicle_type_ids[],custom_vehicle_types[],operating_hours:[7]}`
- Hours item: `{day_of_week:1..7,is_closed,opening_time?,closing_time?}`
- Response: `{garage_id,approval_status,registration_version,submitted_at,latest_decision}`.
- Snapshot must not contain secrets. Include submitted fields and association IDs/names.

## 5. Services — `/services`
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/services` | Public | search?, page=1, limit=20 (max 100) | Active catalog only. 200/422. |
| POST `/services/custom` | Verified owner | `{name}` | 2–100 chars; normalize whitespace; case-insensitive unique against predefined/custom; backend sets creator and `is_predefined=false`. 201/401/403/409/422. |
| GET `/garages/{garage_id}/services` | Public | Path id | Active associations for publicly visible garage. 200/404. |
| POST `/owner/garage/services` | Owner | `{service_ids:[]}` | IDs active; at least one; owner-scoped; validate duplicates; update association set. 200/401/403/404/409/422. |
| DELETE `/owner/garage/services/{service_id}` | Owner | Path id | Cannot remove final active service from approved garage. 200/401/403/404/409. |

## 6. Vehicle types — `/vehicle-types`
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/vehicle-types` | Public | search?, page=1, limit=20 (max 100) | Active catalog only. 200/422. |
| POST `/vehicle-types/custom` | Verified owner | `{name}` | 2–100; normalized case-insensitive uniqueness; creator from JWT. 201/401/403/409/422. |
| GET `/garages/{garage_id}/vehicle-types` | Public | Path id | Active associations for public garage. 200/404. |
| POST `/owner/garage/vehicle-types` | Owner | `{vehicle_type_ids:[]}` | Active IDs; at least one; owner-scoped. 200/401/403/404/409/422. |
| DELETE `/owner/garage/vehicle-types/{vehicle_type_id}` | Owner | Path id | Cannot remove final active type from approved garage. 200/401/403/404/409. |

## 7. Garage profile, hours, availability and photos
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/owner/garage` | Owner | — | Own garage incl status, catalogs, hours, availability, location. 200/401/403/404. |
| PATCH `/owner/garage` | Owner | `phone?`,`description?` | Minor fields only; immediate. Critical fields rejected. 200/401/403/404/422. |
| POST `/owner/garage/profile-change-requests` | Owner | `name?`,`address?`,`latitude?`,`longitude?` | Critical fields only; coordinates paired; no-op rejected; one pending request; current public values unchanged. 201/401/403/404/409/422. |
| GET `/owner/garage/profile-change-requests` | Owner | page?,limit? | Own requests. 200/401/403. |
| GET `/owner/garage/profile-change-requests/{request_id}` | Owner | Path id | Own request detail. 200/401/403/404. |
| GET `/owner/garage/operating-hours` | Owner | — | Seven weekday records. 200/401/403/404. |
| PUT `/owner/garage/operating-hours` | Owner | `hours[7]` | Full replacement; exactly seven unique days; closed => null times; open => both, opening<closing; transaction. 200/401/403/404/422. |
| PATCH `/owner/garage/availability` | Owner | `{is_temporarily_unavailable:boolean,message?:string}` | Manual toggle; message max 300, only while unavailable; clear when false; no expiry. 200/401/403/404/422. |
| GET `/owner/garage/availability` | Owner | — | Override, derived status, timezone, local time, optional next change. 200/401/403/404. |
| POST `/owner/garage/photos` | Owner | multipart `file`, caption? | JPEG/PNG/WebP; max 5MB; inspect actual content; max 10 active; save URL and storage_key. 201/401/403/413/415/422. |
| PATCH `/owner/garage/photos/reorder` | Owner | `{ordered_photo_ids:[]}` | All active and owned; transactionally update display_order. 200/401/403/404/422. |
| DELETE `/owner/garage/photos/{photo_id}` | Owner | Path id | Soft-delete DB row; cloud deletion by storage_key with retry. 200/401/403/404. |

Public photos endpoint is defined under public garage APIs only once.

## 8. Private garage staff management — `/owner/staff`
Staff are internal garage records, not user accounts. The garage owner is the only role that can access the roster and staff details. A garage can have zero staff; the owner may operate independently. Staff belong to one garage in this MVP. Identity for an operation is derived from the authenticated owner's garage, never from a client-supplied `garage_id`.

| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/owner/staff` | Verified owner | — | List all staff, including inactive records, for the owner's garage; return `[]` when the owner has no garage staff. Never expose this collection publicly. 200/401/403/404. |
| POST `/owner/staff` | Verified owner | `full_name,phone,role_title?` | Create active staff record; full_name 2–100, phone E.164, role_title max 50. 201/401/403/404/422. |
| GET `/owner/staff/{staff_id}` | Verified owner | Path id | Return only a staff record belonging to the owner's garage; otherwise 404. 200/401/403/404. |
| PATCH `/owner/staff/{staff_id}` | Verified owner | `full_name?,phone?,role_title?,is_active?` | Update supplied fields; reject empty patch; preserve record. Owner-scoped; otherwise 404. 200/401/403/404/422. |
| DELETE `/owner/staff/{staff_id}` | Verified owner | Path id | Deactivate (`is_active=false`) rather than hard-delete; owner-scoped. 200/401/403/404. |

Staff DTO: `{id,garage_id,full_name,phone,role_title,is_active,created_at,updated_at}`. Responses are available only through owner routes. Do not add staff names or phone numbers to public garage cards, profiles, discovery, customer APIs, or public analytics. Staff are not independently authenticated in this initial CRUD scope.

## 9. Discovery and search
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/garages/nearby` | Public | latitude,longitude; optional search, service_ids[], vehicle_type_ids[], open_now | Apply filters first; search 5 km; if fewer than 3 matching garages expand to 10 km; return up to 3 nearest. Keep original origin regardless of map pan. 200/422. |
| GET `/garages` | Public | latitude?,longitude?,search?,service_ids[],vehicle_type_ids[],open_now?,sort_by?,page=1,limit=10 | Coordinates paired. With coordinates use same 5/10 km fallback after filters, return all matches in radius. Without coordinates list all eligible. Service ANY, vehicle ANY, AND between groups. `open_now` filters derived OPEN. Sort nearest/highest_rated/most_reviewed; nearest requires coordinates. Stable sorting; unrated last. 200/422. |

Use shared discovery query logic for map and list. Public eligibility: approved, not garage-suspended, not deleted, owner ACTIVE. Active catalog entries only. Nearby returns max 3; listing paginates 10.

## 10. Public garage and analytics APIs
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/garages/{garage_id}` | Public | Path id | Public profile: name, description, phone, address, coordinates, timezone, rating/count, availability, services, vehicle types, hours, photos, created_at. 200/404. |
| GET `/garages/{garage_id}/operating-hours` | Public | Path id | Seven-day schedule + timezone. 200/404. |
| GET `/garages/{garage_id}/availability` | Public | Path id | Derived status, override, message only when active, timezone/local time/next change. 200/404. |
| GET `/garages/{garage_id}/photos` | Public | Path id | Active photos ordered by display_order. 200/404. |
| POST `/garages/{garage_id}/analytics/profile-view` | Public, optional auth | No body | Record PROFILE_VIEW; optional customer ID from JWT; dedup/rate-limit refresh inflation; frontend must not block profile. 202/404/429. |
| POST `/garages/{garage_id}/analytics/call-click` | Public, optional auth | No body | Record CALL_CLICK; frontend opens tel: immediately. Click is not confirmed call. 202/404/429. |

## 11. Customer reviews
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| POST `/garages/{garage_id}/reviews` | Verified active customer | `rating` required, `comment?` | Rating integer 1–5; comment optional/null max 2000; cannot review own garage; garage must be public-eligible; temporary unavailable/closed does not block; one active published review. 201/401/403/404/409/422. |
| GET `/garages/{garage_id}/reviews` | Public | page=1,limit=10 max 50, sort newest/highest_rating/lowest_rating | Published, non-deleted only; include average, count, distribution and pagination. Suspended authors' existing published reviews still count. 200/404/422. |
| PATCH `/reviews/{review_id}` | Author, active customer | `rating?`,`comment?` | At least one; independently update; omitted unchanged; null/empty comment clears; no time limit; only published/non-deleted. 200/401/403/404/409/422. |
| DELETE `/reviews/{review_id}` | Author, active customer | Path id | Soft-delete; preserve history; permits later new review. 200/401/403/404. |
| POST `/reviews/{review_id}/reports` | Verified active customer | `reason`,`details?` | Reasons SPAM, ABUSIVE_CONTENT, FAKE_REVIEW, IRRELEVANT, OTHER; cannot report own review; one report per reporter/review; no auto-removal. 201/401/403/404/409/422. |

Review DTO: `{id,customer:{display_name},rating,comment,created_at,updated_at}`. Never return email/phone/private account details. No owner reply. Admin-removed reviews cannot be edited/restored.

## 12. Owner dashboard and analytics
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/owner/dashboard` | Owner | — | Garage summary, approval/availability, views, call clicks, average rating, review count. 200/401/403/404. |
| GET `/owner/analytics/engagement` | Owner | start_date,end_date,group_by=day/week/month | Garage timezone; daily max 90 days; weekly/monthly max 365 days; views/clicks time series. 200/401/403/404/422. |
| GET `/owner/analytics/ratings` | Owner | — | Average, total, 1–5 distribution; exclude deleted/removed. 200/401/403/404. |
| GET `/owner/reviews` | Owner | page,limit<=50,sort | Own garage reviews with display name only. 200/401/403/404/422. |
| GET `/owner/analytics/summary` | Owner | start_date,end_date | Current vs immediately preceding equal-length period; views, clicks, reviews, average. 200/401/403/404/422. |

Garage identity derives from authenticated owner, never arbitrary client-supplied garage ID.

## 13. Admin APIs
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/admin/dashboard` | Admin | — | Counts of users, garages/statuses, reviews, pending reports, call clicks. 200/401/403. |
| GET `/admin/garage-registrations` | Admin | status?,search?,page,limit | Filter/paginate. 200/401/403/422. |
| GET `/admin/garage-registrations/{garage_id}` | Admin | Path id | Owner, details, catalogs, hours, photos and current version. 200/401/403/404. |
| PATCH `/admin/garage-registrations/{garage_id}` | Admin | decision APPROVE/REJECT, expected_version, rejection_reason? | Only PENDING; rejection reason required; atomic status+version check; first valid decision wins; audit/history/notify; no reversal. 200/401/403/404/409/422. |
| GET `/admin/garage-profile-change-requests` | Admin | status?,search?,page,limit | List. 200/401/403/422. |
| PATCH `/admin/garage-profile-change-requests/{request_id}` | Admin | decision,rejection_reason? | Approve applies critical fields and recalculates timezone atomically; reject leaves old data. 200/401/403/404/409/422. |
| GET `/admin/garages` | Admin | search?,status?,suspended?,page,limit | List all moderation states. 200/401/403/422. |
| PATCH `/admin/garages/{garage_id}/moderation` | Admin | action SUSPEND/RESTORE,reason? | Suspend reason required; restore only approved/non-deleted; audit and notify. 200/401/403/404/409/422. |
| DELETE `/admin/garages/{garage_id}` | Admin | reason | Soft-delete, preserve history/reviews/audit; no restore in MVP. 200/401/403/404/409/422. |
| GET `/admin/users` | Admin | role?,account_status?,search?,page,limit | Filter users. 200/401/403/422. |
| GET `/admin/users/{user_id}` | Admin | Path id | User detail + optional garage; no secrets. 200/401/403/404. |
| PATCH `/admin/users/{user_id}/status` | Admin | status ACTIVE/SUSPENDED,reason? | Customer/owner only; cannot suspend self/admin; suspension revokes refresh tokens. Owner suspension hides garage; restore only if garage otherwise eligible. 200/401/403/404/409/422. |
| GET `/admin/review-reports` | Admin | status?,reason?,page,limit | List. 200/401/403/422. |
| GET `/admin/review-reports/{report_id}` | Admin | Path id | Report + review + garage. 200/401/403/404. |
| PATCH `/admin/review-reports/{report_id}` | Admin | decision DISMISS/REMOVE_REVIEW,note | Note required; removal marks review REMOVED, excludes rating, blocks author edit/restore; audit and notify reporter. 200/401/403/404/409/422. |
| GET `/admin/audit-logs` | Admin | admin_id?,action_type?,date range,page,limit | Append-only audit list. 200/401/403/422. |

## 14. Notifications — `/notifications`
| Method & path | Access | Input | Behavior / responses |
|---|---|---|---|
| GET `/notifications` | Authenticated | page=1,limit=20 max 50,is_read? | Always filter by authenticated user. 200/401/422. |
| GET `/notifications/unread-count` | Authenticated | — | Return unread_count. 200/401. |
| PATCH `/notifications/{notification_id}/read` | Authenticated | Path id | Own notification only; idempotent. 200/401/404. |
| PATCH `/notifications/read-all` | Authenticated | — | Mark own notifications read; return updated_count. 200/401. |
| DELETE `/notifications/{notification_id}` | Authenticated | Path id | Delete own notification only. 200/401/404. |

## 15. DTO examples
**Garage card:** `{id,name,latitude,longitude,distance_km,average_rating,review_count,availability,phone,cover_photo_url}`

**Availability:** `{status:"OPEN|CLOSED|TEMPORARILY_UNAVAILABLE",is_temporarily_unavailable,message?,timezone,local_time,next_status_change?}`

**Review:** `{id,customer:{display_name},rating,comment,created_at,updated_at}`

## 16. Engineering decisions to finalize before implementation
- JWT access/refresh lifetimes, password policy and auth rate limits.
- Exact pagination maxima and query parameter array serialization.
- Profile-view/call-click deduplication and abuse prevention.
- Cloud storage provider and deletion retry worker.
- Email provider and notification outbox/retry strategy.
- Exact Pydantic field nullability and enum values.
- Decide whether `/garages/nearby` is a wrapper over shared discovery query logic (recommended).

### Technical plan: remote roadside assistance (not implemented)
The first release is a customer-initiated, garage-owner-managed request. The customer selects a nearby eligible garage, shares a problem summary and approximate location, and sends a request. The garage owner accepts or declines; acceptance unlocks the customer's contact/location details and prompts the owner to call and confirm the problem, price, and response estimate. A request does not promise dispatch or a fixed arrival time.

#### Product decisions to lock before coding
- Define supported service area and whether matching uses a garage-set radius, customer-selected radius, or both. A proposed default is a garage-configured radius capped by the customer's search radius.
- Require explicit roadside opt-in, availability status, service radius, supported vehicle types/services, operating window, and a phone number for callbacks. Normal garage hours and profile visibility do not imply roadside readiness.
- Define response expectation, request expiry, cancellation rules, rate limits, and what the customer sees while waiting. Keep price and ETA as owner-confirmed estimates, not guarantees.
- Before acceptance show only a coarse location (for example a map cell/approximate distance), problem summary, vehicle category, and callback availability. Reveal exact coordinates/address and phone only after acceptance.
- Confirm staff participation is out of scope initially: the garage owner receives and manages requests, and can coordinate with staff offline. Later assignment should reference `garage_staff` while retaining owner authorization.
- Decide abuse reporting, emergency guidance, support ownership, and retention/deletion policy for sensitive location/contact data.

#### Proposed data model
- `roadside_capabilities`: one-to-one with garage; `enabled`, `is_available`, `service_radius_km`, optional availability note, and timestamps. Keep operational availability separate from normal hours and temporary garage unavailability.
- `roadside_requests`: UUID, customer and garage foreign keys, server-generated public request code, status, vehicle type, problem description, coarse location snapshot, encrypted exact latitude/longitude and contact snapshot, optional owner-confirmed quote/ETA, expiry and lifecycle timestamps, created/updated timestamps.
- `roadside_request_events`: append-only transition/audit trail with request, actor, from/to status, timestamp and safe metadata. Avoid copying secret contact/location into events.
- Index active requests by garage/status/created time, customer/status/created time, and use PostGIS geography for eligible-garage radius matching. Add idempotency key per customer submission to prevent duplicate requests.
- Keep new entities in dedicated tables/migration; do not overload analytics events, availability fields, or staff rows.

#### Lifecycle and API proposal
`PENDING → ACCEPTED → CONTACTED → CONFIRMED → IN_PROGRESS → COMPLETED`, with alternate terminal states `DECLINED`, `EXPIRED`, `CANCELLED`, and `UNABLE_TO_SERVE`. Enforce transitions server-side with a conditional update/version check; only the customer can cancel before work begins, and only the assigned garage owner can accept/decline/update service progress. Define transition deadlines before implementation.

| Method & path | Access | Purpose |
|---|---|---|
| GET `/roadside/eligible-garages` | Active customer | Filter approved, non-suspended garages with roadside enabled/available and compatible vehicle/service, by radius and distance. Return only public garage details, approximate distance, availability and callback expectation. |
| POST `/roadside/requests` | Active customer | Create pending request for one eligible garage with vehicle, problem, location and callback phone; validate consent, radius, size and rate limits; return safe summary and expiry. |
| GET `/roadside/requests` | Active customer / garage owner | List only caller's own requests or requests for the owner's garage; redact exact location/phone until accepted. |
| GET `/roadside/requests/{id}` | Participating customer / garage owner | Return lifecycle detail; reveal sensitive fields only to the customer and accepted garage owner. |
| POST `/owner/roadside/requests/{id}/accept` | Garage owner | Atomically accept one still-pending, unexpired request and unlock contact/location. |
| POST `/owner/roadside/requests/{id}/decline` | Garage owner | Decline with a controlled reason; customer gets a status update and can contact another garage. |
| PATCH `/owner/roadside/requests/{id}` | Garage owner | Record contacted/confirmed/in-progress/completed/unable-to-serve and optional confirmed quote/ETA. |
| POST `/roadside/requests/{id}/cancel` | Requesting customer | Cancel before work begins; idempotent and audited. |
| PATCH `/owner/roadside/capability` | Garage owner | Set opt-in, availability, radius and callback expectations; reject unsupported ranges. |

#### Delivery, privacy and frontend sequence
- Persist request and an outbox notification in one transaction; deliver push/email/SMS asynchronously with retry, deduplication and delivery status. Do not depend on a browser session being open. Start with in-app polling/refresh plus delivery fallback; consider WebSockets only if latency needs justify operating them.
- Customer flow: permissioned location or manual pin → eligible list → one garage request → pending state with cancel/expiry → accepted state with callback instructions → confirmed status and owner estimate → completion/cancelled history.
- Owner flow: explicit roadside availability setup → incoming request queue → safe preview → accept/decline → call customer → record confirmation, quote and ETA → progress/completion.
- Store precise location/contact only as long as required by the request and retention policy; redact from logs, analytics, admin summaries and push payloads. Encrypt at rest where supported and never expose it to other garages or public discovery.
- Add metrics for eligible results, requests, response time, accept/decline/expiry, cancellations and completion, without sensitive data.

#### Implementation order and acceptance checks
1. Finalize coverage, timing, cancellation, privacy and support decisions; approve request state diagram and payload redaction matrix.
2. Add migrations/models/schemas, geospatial candidate query, capabilities endpoint, state transition service and audit/outbox handling.
3. Add customer eligible-garage/request/history UI, then owner capability/queue/detail/action UI; show clear loading, empty, offline, expiry, retry and permission-denied states.
4. Add delivery worker/provider integration and operational controls; keep manual refresh/polling as a fallback.
5. Verify role/ownership isolation, pre/post-acceptance redaction, race-safe single acceptance, expiry/cancel boundaries, idempotent creation/transitions, matching radius/filter behavior, notification retries, and mobile/location-permission edge cases.

This is a planning artifact only; no roadside schema, routes or UI should be treated as implemented. Do not infer roadside availability from normal operating hours.
