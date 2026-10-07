# Hosted SaaS local development

This page covers the first hosted API foundation. It does not turn the legacy local scraper into a production SaaS collector. The hosted API currently supports verified Supabase Auth identity and workspace management only.

## Requirements

- Python 3.10+
- A Supabase project configured to issue asymmetric signing-key JWTs
- A PostgreSQL database (Supabase-managed for the proposed pilot)
- A dedicated, least-privilege application database role

The API validates JWT signatures against the Supabase Auth JWKS endpoint and checks issuer, audience, expiry, and subject. Supabase documents JWKS-based verification and recommends a maintained verification library. [Supabase JWT guide](https://supabase.com/docs/guides/auth/jwts) [PyJWT usage](https://pyjwt.readthedocs.io/en/stable/usage.html)

## Configure

Copy `.env.example` to `.env` and set:

- `RADAR_SUPABASE_URL`: project URL, for example `https://<project-ref>.supabase.co`.
- `RADAR_DATABASE_URL`: PostgreSQL SQLAlchemy URL using `postgresql+psycopg` and TLS.

Do not put database credentials or Supabase secret keys in browser code. Do not use a database superuser as the long-running app role. Keep the migration role separate from the API role in deployed environments.

## Apply the hosted schema

```bash
python -m pip install -e ".[dev]"
alembic upgrade head
```

The Alembic environment reads `RADAR_DATABASE_URL`; when absent, it retains the legacy local SQLite path. The new SaaS tables are prefixed `saas_` and do not yet migrate listing data into workspaces.

## Start the API

```bash
uvicorn category_radar.saas.app:app --host 127.0.0.1 --port 8000
```

- `GET /health` is a process liveness check.
- `GET /health/ready` checks database connectivity.
- `GET /api/v1/me` requires a Supabase bearer access token.
- `GET` and `POST /api/v1/workspaces` require a bearer access token.
- `GET /api/v1/workspaces/{workspace_id}` returns 404 for both missing and non-member workspaces.
- `GET` and `POST /api/v1/workspaces/{workspace_id}/projects` manage workspace-owned radar scope (category, two-letter market codes, competitor brands).

Project creation is currently configuration only. It does not start a scrape or generate market insights; collection must be added behind a durable job queue after source permissions and terms have been reviewed.

## Current boundary and next work

All existing listing and analytics routes still belong to the local prototype and are not tenant-scoped. The hosted app deliberately does not mount them. Before any customer collection or analytics route is added, move runs, listings, and reviews into workspace-scoped tables and enforce membership on every query. Add cross-workspace authorization tests before onboarding customer data.

Authentication setup also requires creating the Supabase project and configuring asymmetric JWT signing keys. Until that is done, the hosted API returns a configuration error for authenticated routes.
