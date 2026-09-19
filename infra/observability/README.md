# Observability: dashboards and the signals behind them

Everything here is derived from signals the code **already emits**; nothing
below assumes a metric that doesn't exist. Three sources:

| Source | Emitted by | Carries |
|---|---|---|
| Structured JSON logs (stdout) | `proofhire_api.logging`, every worker stage | `trace_id`, event name, per-event fields (below) |
| OpenTelemetry spans | `proofhire_api.telemetry` + `@traced_stage` on every pipeline stage | one span per stage: `repository_sync`, `evidence_extraction`, `job_analysis`, `coverage_computation`, `generation`, `document_export`; FastAPI auto-instrumented |
| `generation_runs` table | `proofhire_worker.intelligence.generation` | `token_usage`, `latency_ms`, `estimated_cost`, `status`, `prompt_versions`, `model_config_json`, per run |
| Redis | Dramatiq | queue depth per queue (`LLEN dramatiq:{ingest,ai,render}`) |

Status: **not deployed against a live backend.** There is no collector or
Grafana in any environment yet (see `docs/product/BUILD_STATUS.md`). What is
committed is the dashboard as code (`grafana-dashboard.json`) and the SQL that
backs the cost/latency panels, so standing up a backend is configuration, not
design work. Point `OTEL_EXPORTER_OTLP_ENDPOINT` at any OTLP collector and
`SENTRY_DSN` at a project and the sources above light up with no code change.

## The four dashboard rows

**1. Success rate** — per pipeline stage, from span status
(`@traced_stage` records an exception as an errored span) and from log events:
`sync_run_failed`, `job_analysis_failed`, `embedding_failed`,
`secret_scan_flagged` (a *good* event: it counts content kept away from the
LLM).

**2. Latency** — p50/p95 per stage from span duration. For generation
specifically, `generation_runs.latency_ms` gives the same number without a
tracing backend (`queries.sql`).

**3. Cost** — `llm_call_completed` log events carry `provider`, `model`,
`task`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, and
`prompt_version`; `generation_runs.estimated_cost` aggregates per run.
`llm_call_retrying` counts transient provider failures (rate limits, 5xx) by
`provider` and `error_type` — a rising rate there is the early signal that a
spend cap or a provider switch is needed.

**4. Backlog** — Redis `LLEN` per Dramatiq queue. `extraction_skipped_no_changes`
counts syncs that did no LLM work; its ratio to total syncs is the
"incremental-sync reduction" the checklist asks for (Track D "Systems").

## Not covered, on purpose

- No "users online" / product analytics. Out of scope for an ops dashboard.
- No per-user cost panel. `generation_runs.user_id` makes it a one-line
  change, but surfacing per-person spend on a shared ops board is a privacy
  decision, not a dashboard decision.
