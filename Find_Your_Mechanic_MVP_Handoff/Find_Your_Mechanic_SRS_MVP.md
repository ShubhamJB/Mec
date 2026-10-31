# Find Your Mechanic — Software Requirements Specification (MVP)
**Version 1.0 | 30 October 2026 | Team handoff**

## 1. Purpose
This SRS defines the MVP requirements for Find Your Mechanic, a location-based garage discovery platform. It is the baseline for product, UX, frontend, backend, QA and project planning.

## 2. Product overview and goals
Customers discover nearby garages, inspect profiles, call garages directly and submit reviews. Garage owners register and maintain a garage listing subject to admin approval. Administrators approve registrations and moderate listings, users and reviews.

Goals:
- Make relevant garages easy to find using map and list discovery.
- Provide useful and current information: services, vehicle types, location, hours, availability and reviews.
- Give owners basic profile and engagement analytics.
- Give administrators controlled approval and moderation tools.
- Keep the MVP focused and maintainable.

## 3. Actors
| Actor | Capabilities |
|---|---|
| Visitor/customer | Browse, search, filter, view profiles and reviews, call garages without an account. |
| Registered customer | Visitor capabilities; manage own reviews, report reviews, manage profile and notifications. |
| Garage owner | Register one active garage, manage profile/catalog associations/hours/availability/photos, view reviews and analytics. |
| Administrator | Approve/reject registrations and critical profile changes; moderate garages, users and reviews; view audit logs and analytics. |

## 4. MVP scope
### Included
- Customer and owner registration, email verification, login, refresh and logout.
- Public nearby discovery, paginated listing, name search, filters and sorting.
- Garage registration, editing while pending, admin approval and history.
- Garage profile, services, vehicle types, operating hours, temporary availability and photos.
- Public reviews, customer review management and reports.
- Owner dashboard and analytics.
- Admin moderation and in-app/email notifications.
- Optional private garage staff management: an owner may operate alone or maintain staff records; staff are not public accounts or public profile data.

### Excluded
In-app messaging, booking, payments, quotations, job tracking, owner review replies, verified-service reviews, formal in-app suspension appeals, multiple branches per owner, advanced identity/business verification and advanced analytics.

## 5. Functional requirements
1. **Authentication:** Customer/owner registration; backend assigns role. Email verification required before login. Shared login for all roles. JWT access/refresh tokens; refresh tokens stored hashed and rotated. Logout current/all sessions.
2. **Customer profile:** View own profile; update full name; change password after current-password validation. Email changes are out of scope.
3. **Garage registration:** Verified owner submits name, description, E.164 phone, address, coordinates, services, vehicle types, seven-day schedule and optional photos. Backend derives IANA timezone from coordinates. Initial state PENDING.
4. **Pending registration edits:** Owner may edit while PENDING. Update garage record and increment `registration_version`. Preserve original submission snapshot in `garage_registration_history.submission_data`.
5. **Registration decisions:** Admin approves/rejects only PENDING registrations. Rejection reason required. Decision must match expected version and current PENDING state in one transaction. First valid admin decision wins; later decisions return 409. No direct reversal; corrections use separate workflows and preserve history.
6. **Catalogs:** Shared services and vehicle types. Owners may create custom normalized case-insensitive unique entries. Only active catalog entries are public/selectable. Admin deactivation must not leave an approved garage with zero active services or zero active vehicle types.
7. **Garage profile:** Phone and description update immediately. Name, address and coordinates require admin-approved profile change request. Current public profile remains unchanged while request is pending. One pending critical change request per garage.
8. **Operating hours:** Exactly seven records per garage, ISO weekday 1=Monday through 7=Sunday. Each day explicitly open or closed. One continuous interval/day; opening earlier than closing. No overnight hours.
9. **Availability:** Owner manually toggles temporary unavailability; no automatic expiry. Optional customer-facing message up to 300 characters. Temporary state overrides schedule; otherwise OPEN/CLOSED is derived using garage timezone and hours. Clear message when toggle is disabled.
10. **Photos:** Optional 0–10 active photos. JPEG/PNG/WebP, maximum 5 MB, validate actual file content. First ordered active photo is cover. Manual ordering. Soft-delete metadata and delete cloud object using `storage_key`; retry failures.
11. **Discovery:** Public results include only approved, non-suspended, non-deleted garages whose owner account is active. Nearby search uses original customer coordinates, 5 km; if fewer than 3 matching garages, expand to 10 km; return up to 3 nearest markers. Map pan/zoom does not change origin.
12. **Listing/filtering:** Separate list, 10 per page. Search by garage name; multi-select services and vehicle types; Open Now; sort nearest/highest rated/most reviewed. ANY within each filter group, AND between groups. Apply filters before pagination. Map/list filters must agree.
13. **Public profile:** Show name, description, phone, address, map location, timezone, rating/count, availability, services, vehicle types, hours and photos. Do not expose owner email or moderation internals.
14. **Reviews:** Verified active customer; rating 1–5 required; comment optional, max 2,000. Rating-only allowed. No verified-service requirement. Cannot review own garage. One active published review/customer/garage. Edit rating/comment independently at any time; soft-delete own review. Admin-removed review cannot be edited/restored. Temporary unavailability/closed hours do not block reviews.
15. **Review visibility:** Owner sees reviewer display name, rating, comment and date, never email/phone/private account data. Suspended customers' existing published reviews remain visible and count toward rating, but suspended customer cannot submit/edit/delete/report.
16. **Owner analytics:** Profile views, call clicks, average rating, review count and time series. A call click is not a confirmed call. Do not expose browsing history.
17. **Administration:** Manage registrations, critical profile changes, garages, users, review reports and audit logs. Suspend/restore garages and users; soft-delete garages; dismiss reports/remove reviews. Audit all state-changing admin actions.
18. **Notifications:** In-app/email for verification, registration and critical profile decisions, garage/account suspension/restoration; in-app for review received, report submission to admins and report resolution to reporter.
19. **Owner suspension:** Suspended owner hides their garage automatically without changing the garage's independent suspension flag. Restoring owner restores visibility only if garage is otherwise eligible.
20. **Customer suspension:** Suspended customer cannot authenticate or act on reviews; existing published reviews remain visible and count.
21. **Garage staff:** A garage owner may manage zero or more staff members. Staff are optional; the owner can operate the garage alone. Staff records are private to the owning garage owner and never appear in public/customer APIs. Deactivation preserves the record for future work history; no hard delete.

## 6. Business rules
| Area | Rule |
|---|---|
| Public visibility | Approved AND garage not suspended AND not deleted AND owner ACTIVE. |
| Ownership | One non-deleted garage per owner; partial unique index. Soft-deleted garage permits a new registration. |
| Garage name | Not globally unique; duplicates allowed. |
| Location | Owner-selected map pin is authoritative; address is descriptive. PostGIS geography(Point,4326). |
| Timezone | Backend derives IANA timezone from coordinates; recalculate after approved coordinate change. |
| Phone | One primary phone, E.164; international numbers allowed. |
| Critical changes | Name/address/coordinates require approval. |
| Catalog | Shared custom entries, normalized case-insensitive uniqueness; inactive entries hidden and not selectable. |
| Rating | Average/distribution derived from active published reviews. |
| Suspension | Independent from registration approval and temporary availability. |
| Reviews | Partial unique index for active published review; deleted/removed history retained. |
| Garage staff | Optional, single-garage records; owner-only access; deactivate rather than hard-delete. |
| Registration history | Immutable snapshot per submission; pending edits update current garage and version. |

## 7. Non-functional requirements
- Security: RBAC, server-side ownership checks, strong password hashing, hashed tokens, rate limiting, safe upload validation.
- Privacy: no public exposure of emails, private details, tokens or customer browsing history.
- Reliability: transactions for approvals, profile changes, catalog deactivation constraints, review uniqueness and photo ordering.
- Performance: PostGIS GiST index; indexes for status filters, associations, reviews, events and notifications.
- Time: API timestamps UTC ISO 8601; operating-hour values are local wall-clock times in garage IANA timezone.
- Accessibility: map has list alternative; location denial allows manual location entry; use `tel:` links.
- Maintainability: `/api/v1`, OpenAPI, explicit Pydantic DTOs, consistent errors.
- Observability: structured logs, immutable admin audit, retry failed cloud deletions and notification delivery.

## 8. Key workflows
### Customer discovery
1. Request browser location permission; capture original coordinates.
2. Search eligible garages within 5 km after filters; if fewer than 3, expand to 10 km.
3. Return up to 3 nearest map markers; map movement does not change origin.
4. List page is separate, 10 items/page. If denied, allow manual location entry.

### Owner registration
1. Register and verify email.
2. Submit garage, catalogs, hours and optional photos.
3. Derive timezone; create garage, seven hour rows, registration snapshot; set PENDING/version 1.
4. Owner may edit while pending; increment version for every edit.
5. Admin decides against latest version. Rejection reason required; resubmission creates a new snapshot on same garage record.

### Critical profile change
Owner submits name/address/coordinates. Old profile stays public. Admin approval applies proposal atomically and recalculates timezone; rejection leaves old values unchanged.

### Review
Verified active customer submits rating and optional comment. Customer can edit either field independently or soft-delete. Admin may remove a reported review; removed reviews are excluded from ratings and cannot be restored by author.

## 9. Acceptance criteria
- Ineligible garages never appear publicly.
- Nearby uses original coordinates and 5/10 km fallback.
- Approved garage has seven schedule rows and at least one active service and vehicle type.
- Pending registration edits increment version and do not alter original submission snapshot.
- Stale or duplicate admin decisions return 409.
- Rating-only reviews work; suspended customers cannot change reviews; their existing published reviews still count.
- Temporary unavailability overrides hours and may display an optional message.
- Owner review DTO exposes display name only, not private account data.
- Garage owners can create, view, update, deactivate, and list staff for their own garage; a garage with zero staff remains valid and operates under its owner.
- Customers and visitors cannot access staff collection or detail endpoints, and public garage responses contain no staff data.

## 10. Open implementation decisions
Engineering must finalize profile-view/call-click deduplication and rate limits, JWT/refresh expiry, password policy, exact pagination limits, email provider, cloud storage provider and notification retry/outbox strategy. These are implementation details not yet fixed as product requirements.

### Future product direction: roadside assistance
Roadside assistance is a separate follow-on feature, not part of the staff CRUD implementation. The proposed first workflow is a customer request to an explicitly roadside-ready garage, followed by owner acceptance and a phone callback to confirm the problem, price, and response. Regular garage hours do not imply roadside availability. Exact location and customer phone should remain hidden from the garage until acceptance. Matching coverage, response expectations, service radius, request lifecycle, cancellation, pricing, safety, and support responsibilities require product validation before implementation.
