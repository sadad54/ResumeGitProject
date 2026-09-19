# Operations: environments, backup, rollback

Companion to `README.md` (deployment preparation). This covers what happens
*after* something is deployed: how environments are kept apart, how state is
protected, and how a bad release is reversed.

Status: nothing is deployed yet (`docs/product/BUILD_STATUS.md`). Everything
below is exercisable against the local stack today and is written so that the
first real deployment does not have to invent it under pressure.

---

## 1. Environment separation

Three environments, selected purely by environment variables. There is no
code path that inspects the environment name to change behavior except the
two documented below; everything else is configuration.

| | `development` | `staging` | `production` |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `staging` | `production` |
| Postgres | local (`infra/docker/docker-compose.yml`, or WSL 5433) | own instance | own instance, backups on |
| Redis | local | own instance | own instance |
| `DATABASE_URL` / `REDIS_URL` | `.env` | secret store | secret store |
| LLM keys | optional; mock provider if absent | real, **separate** keys | real keys |
| `AUTH_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY` | `.env` values | generated per env | generated per env, **never shared with staging** |
| `SENTRY_DSN` | empty (no-op) | set, `environment=staging` | set, `environment=production` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | empty (no-op) or local collector | set | set |
| `WEB_BASE_URL` / `NEXT_PUBLIC_API_BASE_URL` | localhost | staging origins | production origins |
| CSP dev relaxations (`'unsafe-eval'`, `ws://`) | on | **off** | **off** |

The two behavior switches keyed on environment name:

1. `apps/web/next.config.ts` adds `'unsafe-eval'` and the HMR WebSocket
   origin to the CSP only when `NODE_ENV !== "production"`. A staging build is
   a production build, so it gets the strict policy — staging exists partly to
   catch CSP breakage before users do.
2. `SENTRY_DSN` / `OTEL_EXPORTER_OTLP_ENDPOINT` being empty disables those
   integrations entirely (no-op init). This is what keeps CI and local runs
   from shipping events anywhere.

**Never reuse `TOKEN_ENCRYPTION_KEY` across environments.** It encrypts users'
GitHub OAuth tokens (Fernet). A shared key would let a compromised staging
database decrypt production credentials. Rotating it requires re-encrypting
every `github_connections.token_ref`; there is no rotation tool yet, so
generate it correctly once per environment.

Secret generation:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"          # AUTH_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # TOKEN_ENCRYPTION_KEY
```

---

## 2. What state exists, and what backing it up means

| Store | Contains | Loss impact | Backup |
|---|---|---|---|
| Postgres | everything: users, encrypted GitHub tokens, repositories, source artifacts, evidence graph, jobs, requirements, matches, generated documents and claims, generation telemetry | total | **required** |
| Redis | Dramatiq queues (in-flight jobs), rate-limit counters, revoked-token denylist, SSE pub/sub | queued jobs lost; rate limits reset; **revoked tokens become valid again until they expire** | optional; see below |
| Local export store (`infra/storage/`) | rendered PDF / HTML / plaintext | exports must be regenerated (content is in Postgres) | optional; superseded by object storage |

### Postgres

Use the platform's managed backups where available (RDS/Cloud SQL/Neon/Supabase
all provide point-in-time recovery). Where not:

```bash
# Nightly logical backup. pgvector columns dump as plain text and restore cleanly.
pg_dump "$DATABASE_URL" --format=custom --file="proofhire-$(date -u +%Y%m%dT%H%M%SZ).dump"

# Restore into an empty database that already has the pgvector extension.
pg_restore --dbname="$DATABASE_URL" --no-owner --clean --if-exists proofhire-*.dump
```

`--clean --if-exists` matters: the Alembic `alembic_version` row is part of
the dump, so a restore leaves the schema version correct without a manual
`alembic stamp`.

Retention: 7 daily + 4 weekly is proportionate for this data volume. Test a
restore into a scratch database at least once per environment before trusting
it — a backup that has never been restored is a hypothesis.

### Redis

Redis is treated as **rebuildable, with one caveat**. Losing it drops in-flight
Dramatiq messages (the originating API request already returned 202, so the
user sees a job that never completes; they can re-trigger it) and resets rate
limits. Both are acceptable.

The caveat is the token revocation denylist (`proofhire_api.security.
token_revocation`): losing Redis un-revokes every logged-out session until
those tokens expire on their own (≤ `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` for
access tokens, ≤ `AUTH_REFRESH_TOKEN_EXPIRE_DAYS` for refresh tokens). For
production, enable Redis AOF persistence (`appendonly yes`) so a restart does
not clear it; the compose file already mounts a data volume. If Redis is
*lost* rather than restarted, rotate `AUTH_SECRET_KEY` to invalidate every
token at once — the blunt instrument, but correct.

### Export store

Content is regenerable from `generated_documents.content_json`; the PDF is a
render of it. Not backed up. This store is a local filesystem and is the
reason `README.md` says not to run stateless API replicas yet.

---

## 3. Migrations

Forward-only in practice. Every migration in `apps/api/alembic/versions/` has
a `downgrade()`, but downgrades that drop columns (0008) or tables lose data
and are for development, not for reversing a production release.

Release procedure:

1. Take a backup (§2) — a *fresh* one, not last night's.
2. `alembic upgrade head` against the target database **before** the new
   application version receives traffic. All migrations to date are additive
   (new tables, nullable columns), so the old code keeps working against the
   new schema during the switch.
3. Deploy the application.

**IVFFlat rebuilds need more than the default `maintenance_work_mem`.** The
`ix_evidence_embedding_ivfflat` index over 1536-dim vectors fails to build
with Postgres's 64 MB default once the table has even ~2,000 rows
(`memory required is 65 MB`), found by `apps/api/scripts/benchmark_queries.py`.
Migration 0004 never hit it because it indexed an empty table. Before any
`REINDEX` or a migration that recreates that index on a populated database:
`SET maintenance_work_mem = '512MB';` for the session (or set it in the
migration itself). pgvector's guidance for `lists` is `rows / 1000`; the
current `lists = 100` should be retuned once real row counts are known.

Migrations must stay additive-first. A column rename or drop is done as two
releases: add-and-dual-write, then remove once nothing reads the old column.
This is what makes rollback (§4) a redeploy rather than a restore.

---

## 4. Rollback

**Application rollback = redeploy the previous image.** Images are built per
commit in CI (`.github/workflows/security.yml` builds and scans both). Because
migrations are additive-first (§3), the previous application version runs
correctly against the newer schema, so rolling back the app does **not**
require rolling back the database.

Triggers, decided before deploying rather than during the incident:

- `/health` failing or error rate rising after the deploy → roll back
  immediately, investigate after.
- A migration failing partway → it ran in a transaction (Alembic on Postgres
  uses transactional DDL), so the schema is at the previous version; fix
  forward, do not deploy the app.
- A bad migration that *succeeded* and corrupted data → this is the one case
  that needs the §2 backup. Restore to a scratch database first, compare, then
  decide whether to restore fully or repair in place.

**Database rollback is a restore, not a downgrade.** Do not run `alembic
downgrade` in production; restore the pre-release backup from §3 step 1.

What rollback does *not* undo: LLM calls already made (money already spent),
emails/exports already delivered to users, and Redis state. None of these
have a rollback story because none of them need one.

---

## 5. Health and readiness

- `GET /health` — process is up. Use for liveness.
- `GET /ready` — dependencies reachable. Use for readiness / traffic gating.

A deploy should not receive traffic until `/ready` returns 200 on the new
instance, and the old instance should not be stopped until it does.
