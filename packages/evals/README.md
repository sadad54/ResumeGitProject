# Evaluation harness

Run from the repository root with packages installed, or `PYTHONPATH=packages/evals`:

```bash
python -m proofhire_evals.cli score --dataset packages/evals/fixtures/smoke-gold.jsonl --runs packages/evals/fixtures/smoke-runs.jsonl --output reports/smoke.json
python -m proofhire_evals.cli score --dataset benchmark/gold.jsonl --runs benchmark/openai-runs.jsonl --release --output reports/openai.json
python -m proofhire_evals.cli budget --runs benchmark/measured-costs.jsonl --cases 100
```

The checked-in one-case fixture is **synthetic test data**, not a product quality result. It exists only to exercise scoring, missing-measurement failures, and CI output. No model calls happen in this CLI.

## Labeled data and run contract

One JSON object per line, unique `id`. Gold cases include `family` (swe/frontend/backend/full-stack/ai-ml/data/mlops-devops), `requirements` (canonical requirement IDs), and `evidence_matches` (requirement ID → evidence ID → nonnegative relevance grade). A release case also needs `review: {status: "human_reviewed", reviewer: "..."}`. Preserve actual source JD text, source attribution/license and annotation reasoning in the curated dataset. Human review must be real; never mark generated labels as human-reviewed.

Run records contain the same IDs and independently aligned extracted `requirements`, `ranked_evidence`, and measured counts: `claims`, `unsupported_claims`, `immutable_facts`, `preserved_facts`, `parse_back_attempts`, `parse_back_successes`, `secret_leaks`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`. Unsupported claims/fact preservation need independent adjudication, not the generating model's self-reported verification status. Do not sum only successful runs or omit failure cases. Separate runs by provider and record model/prompt versions.

The scorer reports F1, Recall@5, MRR, nDCG@5, factual-claim and parse-back rates, latency, tokens and cost as JSON. Missing measurements fail gates. `--release` additionally requires 100+ reviewed JDs and all seven role families. Score each provider independently. A smoke pass never certifies release readiness.

## Outstanding phase 9 work

The 100+ real JDs and evidence judgments have **not** been collected/reviewed in this implementation. Live provider evaluation, semantic alignment of extracted requirements to gold IDs, independent output grading and benchmark publication remain to be done.

The budget command requires positive measured costs from **both** providers. It proposes a dollar cap from the maximum observed per-run costs, planned case count and 25% margin. It does not itself enforce a provider spending limit. The nightly live runner must reserve worst-case call cost before dispatch, account for retries, stop before its configured cap, and apply a provider-side limit where available. It is intentionally not wired to spend money without measurements. Existing provider telemetry defaults some estimated costs to zero; calibrate these first rather than treating free-looking measurements as real costs.
