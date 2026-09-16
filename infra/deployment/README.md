# Deployment preparation

The API and web Dockerfiles are built on pushes to master. They have not been deployed by this change.
Supply the API's public URL as the web image build argument `NEXT_PUBLIC_API_BASE_URL` (Next.js embeds it at build time).
Set `WEB_BASE_URL` on the API to the exact frontend origin for CORS.
Run `alembic upgrade head` from `apps/api` in an environment configured for the target Postgres database before switching traffic.
Use Postgres with pgvector, Redis, a persistent volume for the current local PDF store, and separate worker/API processes built from the same API image.

The current renderer still uses local file storage inherited from phase 6. Multi-replica deployment requires the planned object storage/signed URL work, or an explicitly shared volume. Do not deploy stateless replicas and expect exported files to survive.

Pending release gates: staging target/credentials, Docker build verification, full live-provider E2E, measured nightly spend cap, full accessibility audit and Lighthouse budgets. See `docs/product/BUILD_STATUS.md`.
