# Retrieval evaluation on human-labelled job-ad data (E1)

`apps/worker/scripts/eval_skill_retrieval.py` → `retrieval-eval.json` (every
number below, with pinned dataset revisions and SHA-256 checksums).

## The task, and why it's the right proxy

ProofHire's retrieval step matches a job requirement's wording against short,
skill-level evidence text ("Built a FastAPI service with async SQLAlchemy").
The closest public, human-labelled data for that is skill extraction from job
ads: for each job-ad sentence, rank the 13,896 skills of the ESCO taxonomy;
the relevant skills are those human annotators assigned to that sentence.

- **TECH** (338 queries) and **HOUSE** (262): SkillSpan job-ad sentences with
  span-level ESCO labels — Decorte et al., *Design of negative sampling
  strategies for distantly supervised skill extraction*, RecSys-in-HR 2022.
- **TECHWOLF** (326): sentence-level ESCO labels — Decorte et al., *Extreme
  multi-label skill extraction training using large language models*, 2023.
- License: CC BY 4.0. ESCO © European Union, reused with attribution.
- 926 queries in total (sentences with at least one label); labels
  `LABEL NOT PRESENT` / `UNDERSPECIFIED` excluded; 2 gold labels absent from
  the ESCO 1.1.0 list dropped.

Every method runs through the product's own machinery: Postgres full-text
search with the same `tsquery` construction and `ts_rank_cd`, the production
embedding model, and `hybrid_search`'s two-stage fusion (top-50 candidates per
signal, weighted sum with the production weights). The skill-overlap signal
has no counterpart here, so fusion is lexical + vector.

## Results (926 queries, pooled; 95% bootstrap CI)

| Method | Recall@5 | Recall@10 | MRR | nDCG@5 | Queries with no results |
|---|---|---|---|---|---|
| hybrid_or_instr | 0.397 [0.371, 0.425] | 0.479 [0.450, 0.509] | 0.380 [0.356, 0.407] | 0.325 [0.301, 0.350] | 0 |
| **hybrid_or** (production now) | 0.391 [0.363, 0.419] | 0.474 [0.446, 0.501] | 0.379 [0.356, 0.404] | 0.322 [0.299, 0.345] | 0 |
| dense_instr | 0.376 [0.350, 0.404] | 0.456 [0.427, 0.483] | 0.371 [0.344, 0.396] | 0.317 [0.291, 0.341] | 0 |
| dense | 0.367 [0.340, 0.395] | 0.453 [0.425, 0.481] | 0.357 [0.332, 0.383] | 0.305 [0.280, 0.329] | 0 |
| hybrid_prod (production before) | 0.366 [0.339, 0.393] | 0.452 [0.423, 0.481] | 0.357 [0.332, 0.384] | 0.305 [0.281, 0.329] | 0 |
| hybrid_or_rrf | 0.330 [0.301, 0.356] | 0.416 [0.387, 0.443] | 0.318 [0.293, 0.342] | 0.266 [0.243, 0.288] | 0 |
| lexical_or | 0.162 [0.142, 0.184] | 0.225 [0.200, 0.250] | 0.167 [0.149, 0.187] | 0.130 [0.113, 0.148] | 3 |
| lexical_and (production before) | 0.015 [0.009, 0.023] | 0.015 [0.008, 0.025] | 0.012 [0.006, 0.020] | 0.013 [0.007, 0.020] | 908 |
| hash_fallback | 0.001 [0.000, 0.003] | 0.001 [0.000, 0.003] | 0.001 [0.000, 0.004] | 0.001 [0.000, 0.003] | 0 |

Paired over the same queries (resampling queries keeps each pair together):

| Comparison | ΔMRR [95% CI] | ΔRecall@5 [95% CI] |
|---|---|---|
| hybrid_or − hybrid_prod | +0.022 [+0.007, +0.037] | +0.025 [+0.007, +0.043] |
| hybrid_or_instr − hybrid_prod | +0.023 [+0.005, +0.041] | +0.032 [+0.010, +0.052] |
| hybrid_or_instr − hybrid_or | +0.001 [−0.009, +0.011] (n.s.) | +0.006 [−0.008, +0.020] (n.s.) |
| dense_instr − dense | +0.014 [+0.001, +0.028] | +0.009 [−0.006, +0.026] (n.s.) |
| hybrid_or_rrf − hybrid_or | −0.061 [−0.078, −0.046] | −0.061 [−0.081, −0.041] |
| dense − hash_fallback | +0.356 [+0.331, +0.381] | +0.366 [+0.339, +0.396] |

## What it changed

1. **The lexical signal was dead.** `hybrid_search` built its lexical query
   with `plainto_tsquery`, which requires every term of the requirement to
   appear. Real requirement sentences are long: 908 of 926 found nothing, and
   the hybrid ranked exactly as dense retrieval alone. ORing the same lexemes
   (same `ts_rank_cd` ranking) makes lexical retrieval work on its own and
   improves the hybrid significantly. **Shipped** (`_LEXICAL_TSQUERY` in
   `repositories/evidence.py`, with a regression test for a sentence that
   shares only some terms with its evidence).
2. **Weighted-sum fusion is confirmed over RRF** (ADR-0006 had chosen it on
   reasoning alone and deferred to data like this).
3. **The BGE query instruction stays off:** a small gain for dense retrieval
   alone, none in the hybrid, and turning it on would change every cached
   query vector.
4. **The embeddings fix, quantified:** the SHA-256 fallback that every
   deployment without an OpenAI key silently used before ADR-0018 is
   indistinguishable from random ranking (MRR 0.001); the local model reaches
   0.357.

## What this doesn't show

- The corpus is skill labels, not ProofHire evidence, so absolute scores
  won't transfer. The comparisons are the result.
- It measures candidate retrieval, not the LLM reranker that makes the final
  Strong/Partial/Gap call, and not the skill-overlap signal.
- Tuning the fusion weights needs relevance judgments on real evidence, which
  don't exist yet.

Reproduce: `python apps/worker/scripts/eval_skill_retrieval.py` (≈3 minutes
on a laptop CPU; downloads ~1 MB of data on first run, then cached).
