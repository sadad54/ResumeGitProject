# ADR-0006: Hybrid retrieval fusion strategy

## Status
Accepted

## Context
PRD §17 requires combining lexical, vector, and skill/entity-overlap signals into
one ranked candidate list of Evidence for a given Requirement, before an LLM
reranker makes the final Strong/Partial/Gap/Unknown call. Two realistic fusion
approaches:

1. **Weighted sum of normalized scores** — compute each signal on its own scale,
   min-max or otherwise normalize each to roughly [0, 1], then combine as
   `score = w1*lexical + w2*vector + w3*skill_overlap`.
2. **Reciprocal Rank Fusion (RRF)** — rank candidates independently under each
   signal, then combine via `sum(1 / (k + rank_i))` across signals, ignoring the
   raw score magnitudes entirely.

This project does not yet have a populated evidence corpus to run a real
comparative benchmark against (GitHub OAuth registration and real LLM API keys
are still pending user setup as of this writing — see README). This decision is
therefore made on structural grounds and revisited once Phase 9's eval harness
has real labeled data to validate against, rather than from empirical A/B
numbers today.

## Decision
Use **weighted sum of normalized scores** for V1:

- **Lexical**: Postgres full-text search (`to_tsvector('english', ...)` +
  `ts_rank_cd`), backed by a GIN index on a generated tsvector column.
- **Vector**: pgvector cosine similarity (`1 - (embedding <=> query_embedding)`),
  backed by an IVFFlat index (`vector_cosine_ops`) — HNSW is deferred until
  Evidence row counts are large enough that IVFFlat's recall/speed tradeoff
  actually matters; IVFFlat is simpler to tune at V1 scale (PRD §12.3 "don't add
  until query patterns prove it necessary" logic, applied to index choice too).
- **Skill overlap**: count of a Requirement's `normalized` keywords that match an
  Evidence item's linked `Skill.canonical_name`s (via `EvidenceSkill`), normalized
  by keyword count.

Rationale for weighted-sum over RRF:
- **Interpretability**: a weighted sum's inputs and output stay in an
  understandable score space, which matters for the Evidence Coverage Matrix's
  "explanation" column (PRD §18) — RRF's rank-based score is harder to explain to
  a user as "why did this evidence surface."
- **Small candidate sets**: V1's per-requirement candidate pool is expected to be
  small (tens, not thousands, of Evidence rows per user in early usage). RRF's
  main advantage — robustness when signals disagree wildly on absolute score
  scale across large result sets — matters less at this scale; a tunable weighted
  sum is simpler to reason about and adjust.
- **Tunability**: weights (`w1, w2, w3`) are explicit constants that can be
  adjusted once Phase 9's eval harness has Recall@K/nDCG data to tune against,
  without changing the fusion mechanism itself.

Initial weights (revisit once real eval data exists): lexical 0.35, vector 0.45,
skill overlap 0.20 — vector similarity weighted highest since it best captures
semantic relevance beyond exact keyword match, which is the main reason to have
a hybrid retriever at all over pure lexical search.

## Consequences
- `EvidenceRepository.hybrid_search` computes and combines all three signals in
  one SQL query per requirement (via SQLAlchemy, not raw hand-written SQL, to
  stay within the existing repository abstraction).
- Migration 0004 adds a generated `search_vector` tsvector column + GIN index on
  `evidence`, and an IVFFlat index on `evidence.embedding`.
- Revisit this ADR once Phase 9's benchmark can empirically compare weighted-sum
  vs. RRF vs. alternative weight values on real labeled data — treat the weights
  above as a documented starting point, not a final tuned value.
