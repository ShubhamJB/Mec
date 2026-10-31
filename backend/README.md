# Local development

Start the database, then run the one-shot seed service to apply migrations, create the local demo data, and print the demo credentials:

```sh
docker compose up -d db
docker compose --profile tools run --rm seed
docker compose up -d --build api web
```

The seed command prints the admin and demo garage-owner UUIDs, login emails, and the shared password. By default, all seeded accounts use `MechaRoadside2026!`. Set `SEED_PASSWORD` in `backend/.env` to choose another local password.

The demo owner is `owner0002@seed.example.com`; the seed data enables roadside assistance for that garage. The admin is `admin@seed.example.com`. The same password is applied to the seeded admin, owners, and customers.

Running the seed command again does not duplicate seed rows. It resets passwords for existing `@seed.example.com` users to `SEED_PASSWORD` and prints the admin and demo-owner account IDs again. This is intended for local development only.

The seed service runs Alembic migrations before seeding. Keep the `tools` profile command for local development; do not use the shared demo password for a deployed environment.
