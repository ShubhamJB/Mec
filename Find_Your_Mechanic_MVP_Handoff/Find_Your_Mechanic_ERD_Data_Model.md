# Find Your Mechanic — ERD and Database Design
**Version 1.0 | PostgreSQL + PostGIS | 17 core entities**

## Conventions
- UUID primary keys; timestamps are `timestamptz` UTC.
- Soft deletion for garages, users/reviews/photos where history is needed.
- `garages.location` is PostGIS `geography(Point,4326)` with GiST index.
- Public OPEN/CLOSED state is derived, not stored as authoritative state.
- Use `ON DELETE RESTRICT` for history-bearing records; do not cascade-delete reviews or audit logs.

## Core entities (17)
1. **users** — id, full_name, normalized unique email, password_hash, role, email_verified, account_status, created_at, updated_at, deleted_at.
2. **garages** — id, owner_id, name, description, E.164 phone, address, location, timezone, approval_status, is_suspended, is_temporarily_unavailable, temporary_unavailability_message (varchar 300 nullable), registration_version, timestamps, deleted_at.
3. **garage_registration_history** — id, garage_id, reviewed_by nullable, status, submitted_at, reviewed_at, rejection_reason, submission_data JSONB immutable snapshot.
4. **services** — id, name, is_predefined, created_by_user_id nullable, is_active, created_at.
5. **garage_services** — garage_id, service_id, created_at; composite PK.
6. **vehicle_types** — id, name, is_predefined, created_by_user_id nullable, is_active, created_at.
7. **garage_vehicle_types** — garage_id, vehicle_type_id, created_at; composite PK.
8. **operating_hours** — id, garage_id, ISO day_of_week, is_closed, opening_time, closing_time; unique garage/day.
9. **garage_photos** — id, garage_id, url, storage_key, caption, display_order, deleted_at, created_at.
10. **reviews** — id, garage_id, customer_id, rating, comment nullable, status PUBLISHED/REMOVED, created_at, updated_at, deleted_at, removed_at, removed_by nullable.
11. **review_reports** — id, review_id, reporter_id, reason, details nullable, status, reviewed_by, admin_note, reviewed_at, created_at; unique review/reporter.
12. **notifications** — id, user_id, title, message, notification_type, related_entity_type/id, is_read, read_at, created_at.
13. **analytics_events** — id, garage_id, customer_id nullable, event_type PROFILE_VIEW/CALL_CLICK, created_at.
14. **admin_actions** — id, admin_id, action_type, target_type, target_id, reason, created_at; append-only.
15. **refresh_tokens** — id, user_id, token_hash, expires_at, revoked_at, created_at, device_info.
16. **email_verification_tokens** — id, user_id, token_hash, expires_at, used_at, revoked_at, created_at.
17. **garage_profile_change_requests** — id, garage_id, submitted_by, proposed_changes JSONB, status, rejection_reason, reviewed_by, submitted_at, reviewed_at.

## Relationships
- User owns 0..1 non-deleted garage; soft-deleted historical rows may remain.
- Garage has many registration history rows, hours, photos, reviews, analytics events and profile change requests.
- Garage↔services and garage↔vehicle types are many-to-many via junction tables.
- User authors reviews, reports, notifications, sessions and verification tokens.
- Review has many reports; one report per reporter/review.
- Admin user creates audit actions and reviews registrations/profile-change requests.

## Important constraints and indexes
```sql
CREATE UNIQUE INDEX uq_active_garage_per_owner
ON garages(owner_id) WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX uq_active_customer_garage_review
ON reviews(garage_id, customer_id)
WHERE deleted_at IS NULL AND status = 'PUBLISHED';

CREATE UNIQUE INDEX uq_pending_profile_change
ON garage_profile_change_requests(garage_id)
WHERE status = 'PENDING';

CREATE INDEX ix_garages_location
ON garages USING GIST(location);

CREATE UNIQUE INDEX uq_operating_hours_day
ON operating_hours(garage_id, day_of_week);

CREATE UNIQUE INDEX uq_active_photo_order
ON garage_photos(garage_id, display_order)
WHERE deleted_at IS NULL;
```
Catalog normalized name uniqueness should use a normalized column or unique index on `lower(trim(name))`; normalize repeated whitespace in application logic.

## Modeling notes
- Owner suspension does not change `garages.is_suspended`; public visibility checks both owner account and garage moderation state.
- Temporary unavailability is independent from approval/moderation.
- Timezone is backend-derived from coordinates; recalculate on approved coordinate change.
- Registration snapshots are immutable; pending edits update garage and increment `registration_version`.
- Rating average/distribution derive from active published reviews.
- `storage_key` is required for cloud photo deletion; URL alone is insufficient.
- The partial review unique index allows a new review after customer deletion or admin removal while retaining old rows.
- Catalog deactivation must transactionally ensure approved garages retain at least one active service/type.
- Optional future reliability table: `notification_deliveries` or `outbox_events`; not included in the 17 core entities.

## Mermaid source
See `find_your_mechanic_erd.mmd` in this package.
