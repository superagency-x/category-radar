# ADR-002: Hosted micro-SaaS architecture

**Status:** Proposed for the first paid pilot  
**Date:** 2026-10-08  
**Owner:** Berk Saraloglu

## Context

Category Radar is changing from a local research pipeline and public static dashboard into a hosted product for marketers and GTM leaders. The first product is a multi-customer, single-workspace-per-customer SaaS with scheduled category snapshots and evidence-backed reports.

The existing Python adapters, normalizer, analytics, and report generation are valuable domain code. The current SQLite store, local `launchd` schedule, public `radar.json`, and Git-push publishing flow are not a safe hosted multi-customer foundation. The API currently has no authentication or tenant boundary.

Data-source terms and commercial use still require source-by-source review. This architecture does not make an otherwise restricted collection permissible.

## Decision

For the first hosted pilot, use a small managed stack and keep the product in one deployable codebase:

- **Application/API:** extend the existing FastAPI/Python service.
- **Web UI:** replace the static public dashboard experience with an authenticated app served on the same site origin. Keep the existing visualizations and analytics where they help.
- **Identity:** Supabase Auth. Verify access tokens in the API with a maintained JWT/JWKS library; never trust unsigned or decoded-only claims.
- **Primary database:** Supabase-managed PostgreSQL in an EU region. Use Alembic as the single schema migration mechanism. SQLite remains for local development and fixture analysis only.
- **Tenant boundary:** workspace and membership records; every customer-owned record is workspace-scoped. Enforce authorization in the service/query layer and add PostgreSQL row-level security as a second boundary. Background workers use explicit workspace-scoped job payloads.
- **Collection:** separate scheduled/background worker process from the request-serving API. Use a Postgres-backed job queue for the low-volume pilot so a separate Redis service is not needed. Jobs are idempotent, retryable, observable, and retain per-source outcomes.
- **Raw evidence:** private object storage with short, configurable retention. Do not place raw pages or customer exports in a public website directory or Git history.
- **Billing:** Stripe Checkout and Customer Portal for subscriptions after the pilot offer and price are validated. The backend, not the browser, owns subscription state and entitlement checks.
- **Deployment:** Render web service and worker in an EU region; Supabase handles managed Postgres, Auth, and private storage. Keep hosting behind environment-based configuration so the provider can be changed later.

This is a deliberately small system: one API/web process, one worker, one managed database/auth provider, one billing provider. No microservices and no customer-specific scraper deployments.

## Initial operating-cost envelope

Current public pricing shows Supabase Pro starting at $25/month and Render's smallest always-on web/background service plans at $7/month each. A simple baseline is therefore approximately **$39/month** before email, domain, usage overages, tax, and source-data costs. This is a planning estimate, not a quote; recheck prices and region availability before deployment. Free tiers are suitable for development only, not the paid service's reliability promise. [Supabase pricing](https://supabase.com/pricing) [Render pricing](https://render.com/pricing)

Supabase's documentation describes JWKS-based token verification and recommends using a high-quality JWT verification library rather than implementing signature verification. [Supabase JWT guide](https://supabase.com/docs/guides/auth/jwts)

## Required data model

At minimum:

```text
users (provider subject is the stable external identity)
workspaces
workspace_memberships (workspace, user, role, created_at)
category_definitions (workspace, config version, category settings)
market_selections (workspace, category, supported market)
source_connectors (source, allowed purpose, status, terms-review reference)
collection_runs (workspace, category, snapshot date, status, started/finished)
collection_run_sources (run, source, market, status, counts, freshness, error class)
listings / reviews / normalized evidence (workspace, run, source, market, provenance)
subscriptions (workspace, provider customer/subscription ids, entitlement state)
audit_events (workspace, actor, action, target, time)
```

Tenant IDs must be included in primary/unique keys and foreign-key relationships where practical. Every route that reads or writes customer data must resolve a verified user and an authorized workspace before data access. A user-supplied workspace ID is only a selector; membership must be verified server-side.

## Collection and publication rules

- Do not launch a paid source until its terms and intended commercial use have been reviewed and recorded.
- Keep a connector allowlist; customers cannot submit arbitrary URLs in the pilot.
- Honor source-specific access restrictions and conservative request limits. Do not use CAPTCHA or bot-wall circumvention.
- Avoid collecting review author names, profile links, or other unnecessary personal data. Prefer derived themes and counts; set short retention for raw evidence.
- Keep the last successful snapshot visible if a later refresh is partial. Clearly mark stale or incomplete markets and never silently represent a partial run as complete.
- Every result includes `as_of`, source, market, collection status, sample size, and metric-version metadata.
- Call rank-based measures “listing visibility” or similar; reserve “sales/share/demand” language for appropriately licensed and representative data.

## Security baseline before a paid pilot

- Verified authentication, short-lived sessions, email verification, password reset, and account deletion flow.
- Workspace membership checks on every request; tests for cross-workspace access denial before real customer data is onboarded.
- RLS policies deny by default and are exercised using the same roles and JWT claims as production.
- Service secrets kept out of the client bundle and repository; rotateable secret storage in deployment environment.
- TLS, secure cookie/session handling, CSRF protection where cookies are used, input validation, rate limits, and a restrictive content-security policy.
- Automated database backups and a documented restore rehearsal; deletion/retention jobs for customer and source data.
- Operational logs with run/workspace IDs but no bearer tokens, credentials, raw review text, or unnecessary personal data.
- Privacy notice, terms, processor agreements as applicable, incident process, and counsel review for data sources and commercial reuse.

## Migration plan

1. Keep the local prototype usable while separating domain analytics from SQLite-specific storage.
2. Define SQLAlchemy/Postgres models and a forward-only migration path. Do not assume the current Alembic migration is authoritative: `Store` still creates SQLite tables directly.
3. Introduce repository/service boundaries and workspace-scoped queries; seed one internal workspace for migration of the current demo dataset.
4. Add authentication and workspace authorization before exposing any customer dataset through the hosted API.
5. Move collection to durable background jobs and private evidence storage; deploy one approved source in staging.
6. Add the authenticated app and report flow, then billing after design-partner validation.
7. Run a limited paid pilot only after source review, isolation checks, backup/restore, and operations runbooks pass.

## Consequences

**Benefits:** low operational burden, modest predictable starting cost, shared scheduled collection, managed authentication, auditable workspace access, and a path to licensed data connectors.

**Costs and risks:** vendor dependency, data-rights uncertainty, more complex operations than the local app, and the need to build a real tenant security model. The present `Store` and Alembic setup are not a ready-made Postgres migration; they must be reconciled before deployment.

## Revisit when

- Customer count or workload requires a separate queue/cache service.
- A source requires a licensed feed or provider-controlled connector.
- Enterprise customers require SSO, audit exports, custom retention, or contractual SLAs.
- Unit economics do not support the managed-service baseline and collection cost per workspace.
