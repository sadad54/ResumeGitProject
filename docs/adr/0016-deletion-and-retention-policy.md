# ADR-0016: Deletion and retention policy

## Status

Accepted.

## Context

The domain has three materially different kinds of "delete", and the checklist
(§13 "Soft/hard deletion policy") requires the choice to be explicit rather
than implied by whichever `ondelete` clause happened to be written first.

Until now the schema had cascades but no stated policy, so it was unclear
whether rejecting evidence was meant to destroy it, whether disconnecting
GitHub should erase derived evidence, and what account deletion actually
guaranteed.

## Decision

**1. Evidence review is a soft state transition, never a delete.**

Rejecting or privatising evidence sets `Evidence.status` (`rejected` /
`private`); the row, its `EvidenceSource` provenance and its content hashes all
remain. Reasons:

- Provenance is the product. A `GeneratedClaim` may cite evidence that the user
  later rejects; if the row vanished, previously exported documents would lose
  the audit trail that justifies them.
- Rejection is a signal, not a mistake to erase — re-running extraction must be
  able to see that the user already rejected an equivalent claim rather than
  re-surfacing it every sync.
- `rejected` evidence is excluded from retrieval in SQL
  (`hybrid_search`: `WHERE ... e.status != 'rejected'`), so soft state has the
  same practical effect as deletion for matching, without losing history.

**2. Stale evidence is marked, not deleted.**

When a source artifact's content hash changes, dependent evidence becomes
`stale` rather than being removed, so a re-sync can re-verify it against the new
content instead of discarding a confirmed decision the user already made.

**3. GitHub disconnect is a scoped hard delete.**

`DELETE /api/v1/github/connection` removes the encrypted OAuth token and the
`Repository` rows it authorised, because retaining a credential the user has
revoked is precisely what they asked us not to do. Derived `Evidence` is
**kept**: it is part of the user's profile, was reviewed by them, and is no
longer reachable through the third-party credential. Destroying a reviewed
evidence graph as a side effect of rotating a token would be a surprising and
unrecoverable loss.

**4. Account deletion is an unconditional hard delete.**

`DELETE /api/v1/auth/me` deletes the `users` row; every owned table cascades
from it (`ondelete="CASCADE"`). No soft-delete tombstone is kept, because this
is the user's own data-erasure path — a "deleted" account whose rows still sat
in the database would defeat the purpose and would be the wrong answer to a
data-subject erasure request.

Rendered exports live in object storage under `users/<user_id>/`
(`services/object_storage.py`), outside the database, so the endpoint deletes
that prefix first and only then the row. If storage is unreachable the request
fails with nothing deleted; the reverse order could strand files with no
account left to reach them through.

**5. Token revocation is time-bounded, not permanent.**

Revoked token ids live in Redis with a TTL equal to the token's own remaining
lifetime (`proofhire_api.security.token_revocation`). Keeping them longer would
grow an unbounded denylist to no benefit: once the token would have expired
anyway, the signature check rejects it regardless.

## Consequences

- No `deleted_at` column exists anywhere, deliberately. Queries do not need to
  filter soft-deleted rows, which removes a common source of data leaks where
  one forgotten `WHERE deleted_at IS NULL` exposes deleted data.
- Account deletion is irreversible and unrecoverable by support. That is the
  intended guarantee, and it is stated in the endpoint's docstring.
- ~~Known gap: account deletion did not purge rendered exports.~~ Closed
  2026-09-27: exports moved to owner-prefixed object-storage keys and deletion
  removes the prefix before the row (`test_account_deletion_purges_exported_files`).
  Exports written before that change used absolute local paths outside any
  prefix; they only ever existed in local development databases.
- Rejected evidence retains the original extracted text. If a user rejects
  evidence *because* it contains something they consider sensitive, they
  currently have to delete the account to purge it. A future
  `DELETE /evidence/{id}` hard-delete path would close that, and is the one
  place where the soft-delete default is arguably wrong.
