-- Dashboard queries against generation_runs (Postgres). Every column referenced
-- exists in apps/api/proofhire_api/models/generation_run.py.

-- Generation latency: p50 / p95 / p99 over the last 24h.
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_ms,
  count(*)                                                AS runs
FROM generation_runs
WHERE created_at > now() - interval '24 hours'
  AND latency_ms IS NOT NULL;

-- Success rate per day.
SELECT
  date_trunc('day', created_at)                                            AS day,
  count(*) FILTER (WHERE status = 'completed')::float / NULLIF(count(*), 0) AS success_rate,
  count(*)                                                                 AS runs
FROM generation_runs
GROUP BY 1 ORDER BY 1 DESC;

-- Cost per application (one generation run = one tailored document set).
SELECT
  date_trunc('day', created_at) AS day,
  sum(estimated_cost)           AS total_cost_usd,
  avg(estimated_cost)           AS cost_per_application_usd,
  count(*)                      AS runs
FROM generation_runs
WHERE estimated_cost IS NOT NULL
GROUP BY 1 ORDER BY 1 DESC;

-- Tokens per application, split by direction. token_usage is JSON with
-- input_tokens / output_tokens totals per run.
SELECT
  date_trunc('day', created_at)                          AS day,
  avg((token_usage->>'input_tokens')::int)               AS avg_input_tokens,
  avg((token_usage->>'output_tokens')::int)              AS avg_output_tokens,
  max((token_usage->>'input_tokens')::int
      + (token_usage->>'output_tokens')::int)            AS max_total_tokens
FROM generation_runs
WHERE token_usage IS NOT NULL
GROUP BY 1 ORDER BY 1 DESC;

-- Prompt-version mix: which prompt versions are live, to correlate a metric
-- shift with a prompt change.
-- prompt_versions is `json` (no equality operator), so group on its text form.
SELECT prompt_versions::text AS prompt_versions, count(*) AS runs, avg(latency_ms) AS avg_latency_ms
FROM generation_runs
WHERE created_at > now() - interval '7 days'
GROUP BY 1 ORDER BY runs DESC;
