# ADR-0013: GitHub OAuth (not GitHub App) for V1

## Status
Accepted

## Context
PRD §12.3 leaves GitHub connection as "OAuth/GitHub App" without deciding. The two
options trade off differently:
- **OAuth (user-token-scoped):** simpler to implement, matches the PRD's own default
  phrasing ("GitHub OAuth separate from application auth"), standard per-user rate
  limits (5,000 req/hr authenticated).
- **GitHub App (installation-scoped):** higher/installation-based rate limits, native
  support for webhook-driven incremental sync (a V1.5 feature per PRD §8.2), but adds
  installation-management complexity (app manifest, installation tokens, permission
  requests separate from user OAuth) not needed for V1's SHA-based manual/on-demand
  sync (PRD §15 Stage 8).

## Decision
Use standard GitHub OAuth for V1. Repository sync in V1 is SHA/content-hash based and
user-triggered (`POST /github/sync`), not webhook-driven, so GitHub App's main V1.5
advantage (webhooks) is not yet needed. OAuth token is stored encrypted
(`GitHubConnection.token_ref`, never plaintext) per PRD §27.

## Consequences
- Faster to implement for V1; one fewer moving part (no app installation flow).
- Rate limits are per-authenticated-user (5,000/hr), which is expected to be
  sufficient for the fixture-repo-scale ingestion volumes targeted in V1.
- Migrating to a GitHub App is the natural path when V1.5 webhook-based incremental
  refresh is built (PRD §8.2) — this is a known, scoped future migration, not a
  design dead-end. Revisit rate-limit headroom with real numbers if/when V1.5 work
  begins.
