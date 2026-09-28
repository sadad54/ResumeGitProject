"""Live end-to-end run of the real pipeline, through the public HTTP API.

Does what a browser does, against a running API + worker with real
providers: sign up -> connect GitHub -> refresh repositories -> select ->
sync (watching the SSE stream) -> wait for evidence extraction -> capture a
job description -> analyze -> wait for coverage -> generate a resume
(SSE) -> read claims -> export -> download through the signed URL -> check
the PDF. Writes timings, counts, and the generation run's token usage to a
JSON report.

The one step not done over HTTP is the GitHub connection: OAuth needs a
person at github.com. The script stores the token the way the OAuth
callback would (Fernet-encrypted, routers/github.py) for a throwaway user,
and deletes that user — token included — at the end (unless --keep).

    GITHUB_E2E_TOKEN=... python scripts/e2e_live.py --repo owner/a --repo owner/b \\
        --worker-log .dev/logs/worker.log --out docs/product/metrics/e2e-live.json

With --worker-log, every `llm_call_completed` event the worker logs during the
run is summed per task (calls, tokens, latency): the pipeline's real token
cost per application, which the API alone does not expose.

The token is read from the environment only; it is never printed or written
anywhere except its encrypted form in the database, for the length of the run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "apps" / "worker"))

SETTLED = {"completed", "failed"}

SAMPLE_JD = """\
AI Engineer — LLM Applications (Fictional sample job description)

We build LLM-powered tools for knowledge workers and are hiring an AI
engineer to take agentic features from prototype to production.

What you'll do
- Design and build LLM agents that plan multi-step tasks and call tools
- Build Python services and APIs around model calls, with structured output
  and validation
- Evaluate model quality with test sets and automated checks
- Ship features end to end, including tests and CI

Required
- Strong Python
- Experience building applications on LLM APIs (OpenAI, Anthropic, Groq or
  similar), including prompt design and structured outputs
- Experience with agent frameworks or building tool-calling agents
- Writing automated tests

Preferred
- FastAPI or another Python web framework
- Retrieval-augmented generation and vector search
- Docker and GitHub Actions
- Experience deploying ML or LLM systems to production
"""


class Step:
    """Times a named stage and records it in the report."""

    def __init__(self, report: dict, name: str) -> None:
        self.report, self.name = report, name

    def __enter__(self):
        self.t0 = time.perf_counter()
        print(f"--> {self.name}", flush=True)
        return self

    def __exit__(self, *exc):
        seconds = round(time.perf_counter() - self.t0, 1)
        self.report["stages"][self.name] = seconds
        print(f"    {self.name}: {seconds}s", flush=True)


def sse_events(client: httpx.Client, run_id: str, until: set[str], timeout: float):
    """Yield (event, data) from the run's SSE stream until a terminal event."""
    deadline = time.monotonic() + timeout
    with client.stream(
        "GET",
        f"/api/v1/events/runs/{run_id}",
        headers={"Accept": "text/event-stream"},
        timeout=httpx.Timeout(timeout, read=60.0),
    ) as response:
        response.raise_for_status()
        event, data = "message", []
        for line in response.iter_lines():
            if time.monotonic() > deadline:
                raise TimeoutError(f"no terminal event within {timeout}s")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip())
            elif line == "":
                if data:
                    payload = json.loads("\n".join(data))
                    yield event, payload
                    if event in until:
                        return
                event, data = "message", []


def wait_for(fetch, done, *, timeout: float, interval: float, what: str):
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        if done(value):
            return value
        if time.monotonic() > deadline:
            raise TimeoutError(f"timed out waiting for {what}")
        time.sleep(interval)


async def connect_github(user_id: str, token: str) -> None:
    from proofhire_api.db import async_session_factory
    from proofhire_api.models.github_connection import GitHubConnection
    from proofhire_api.security.token_crypto import encrypt_token
    from sqlalchemy import select

    async with httpx.AsyncClient(timeout=20) as gh:
        me = (
            (
                await gh.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
            )
            .raise_for_status()
            .json()
        )
    async with async_session_factory() as session:
        uid = uuid.UUID(user_id)
        existing = await session.scalar(
            select(GitHubConnection).where(GitHubConnection.user_id == uid)
        )
        if existing is None:
            session.add(
                GitHubConnection(
                    user_id=uid,
                    github_user_id=me["id"],
                    login=me["login"],
                    token_ref=encrypt_token(token),
                    scopes=[],
                )
            )
        await session.commit()


def llm_usage(log_path: Path, offset: int) -> dict:
    """Sum the worker's llm_call_completed log events written after `offset`."""
    per_task: dict[str, dict] = {}
    with log_path.open("rb") as f:
        f.seek(offset)
        for raw in f:
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if event.get("message") != "llm_call_completed":
                continue
            task = per_task.setdefault(
                event.get("task", "?"),
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latency_ms": 0.0,
                    "models": set(),
                },
            )
            task["calls"] += 1
            task["input_tokens"] += int(event.get("input_tokens") or 0)
            task["output_tokens"] += int(event.get("output_tokens") or 0)
            task["latency_ms"] += float(event.get("latency_ms") or 0)
            task["models"].add(event.get("model"))
    for task in per_task.values():
        task["models"] = sorted(m for m in task["models"] if m)
        task["latency_ms"] = round(task["latency_ms"])
    totals = {
        "calls": sum(t["calls"] for t in per_task.values()),
        "input_tokens": sum(t["input_tokens"] for t in per_task.values()),
        "output_tokens": sum(t["output_tokens"] for t in per_task.values()),
    }
    return {"per_task": per_task, "totals": totals}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--api", default=os.environ.get("E2E_API_URL", "http://localhost:8000"))
    ap.add_argument(
        "--repo",
        action="append",
        required=True,
        help="owner/name of a repository the token can read; repeat for several",
    )
    ap.add_argument("--jd-file", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--keep", action="store_true", help="keep the throwaway user and its data")
    ap.add_argument(
        "--worker-log",
        type=Path,
        default=None,
        help="the worker's JSON log, to total LLM calls and tokens for this run",
    )
    args = ap.parse_args()

    token = os.environ.get("GITHUB_E2E_TOKEN", "")
    if not token:
        sys.exit("GITHUB_E2E_TOKEN is not set")
    jd_text = args.jd_file.read_text() if args.jd_file else SAMPLE_JD
    log_offset = args.worker_log.stat().st_size if args.worker_log else 0

    from proofhire_worker.intelligence.embeddings import build_embedding_provider
    from proofhire_worker.intelligence.model_selection import (
        provider_name,
        resolved_models,
    )

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "api": args.api,
        "repositories": args.repo,
        "llm_provider": provider_name(),
        "models": resolved_models(),
        "embedding_model": build_embedding_provider().model_id,
        "stages": {},
    }
    client = httpx.Client(base_url=args.api, timeout=60)
    email = f"e2e-{uuid.uuid4().hex[:10]}@example.com"
    auth: dict[str, str] = {}
    try:
        with Step(report, "signup"):
            tokens = (
                client.post(
                    "/api/v1/auth/signup", json={"email": email, "password": uuid.uuid4().hex}
                )
                .raise_for_status()
                .json()
            )
            client.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            auth = dict(client.headers)
            user = client.get("/api/v1/auth/me").raise_for_status().json()

        with Step(report, "connect_github"):
            asyncio.run(connect_github(user["id"], token))
            overview = client.get("/api/v1/me/overview").raise_for_status().json()
            assert overview["github"]["connected"], overview

        with Step(report, "refresh_repositories"):
            listed = client.post("/api/v1/github/repositories/refresh").raise_for_status().json()
            by_name = {f"{r['owner']}/{r['name']}".lower(): r for r in listed}
            repos = [by_name[full.lower()] for full in args.repo]
            for repo in repos:
                client.patch(
                    f"/api/v1/github/repositories/{repo['id']}", json={"selected": True}
                ).raise_for_status()
            names = {r["id"]: f"{r['owner']}/{r['name']}" for r in repos}

        with Step(report, "sync"):
            run = (
                client.post("/api/v1/github/sync", json={"repository_ids": list(names)})
                .raise_for_status()
                .json()
            )
            events = Counter()
            per_repo: dict = {}
            for event, data in sse_events(
                client, run["run_id"], {"github.sync.completed", "github.sync.failed"}, 900
            ):
                events[event] += 1
                if event == "github.repo.completed":
                    per_repo[names.get(data["repository_id"], data["repository_id"])] = {
                        k: v for k, v in data.items() if k != "repository_id"
                    }
            report["sync"] = {"events": dict(events), "repositories": per_repo}
            if events["github.sync.failed"]:
                raise RuntimeError(f"sync failed: {report['sync']}")

        with Step(report, "evidence_extraction"):
            # Each repository settles out of `extracting` when its extraction
            # actor finishes (test_extraction_status).
            deadline = time.monotonic() + 5400
            last = None
            while True:
                listed = client.get("/api/v1/github/repositories").raise_for_status().json()
                statuses = {names[r["id"]]: r["sync_status"] for r in listed if r["id"] in names}
                count = len(client.get("/api/v1/evidence").raise_for_status().json())
                if (statuses, count) != last:
                    print(f"    {statuses} · evidence so far: {count}", flush=True)
                    last = (statuses, count)
                if all(s in SETTLED for s in statuses.values()):
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError(f"extraction unsettled after 90 minutes: {statuses}")
                time.sleep(10)
            evidence = client.get("/api/v1/evidence").raise_for_status().json()
            report["evidence"] = {
                "count": len(evidence),
                "repository_status": statuses,
                "by_type": dict(Counter(e["evidence_type"] for e in evidence)),
                "examples": [e["title"] for e in evidence[:10]],
            }
            if not evidence:
                raise RuntimeError(f"no evidence extracted: {statuses}")

        with Step(report, "analyze_job"):
            job = (
                client.post(
                    "/api/v1/jobs/capture",
                    json={
                        "selected_text": jd_text,
                        "captured_at": datetime.now(UTC).isoformat(),
                    },
                )
                .raise_for_status()
                .json()
            )
            client.post(f"/api/v1/jobs/{job['id']}/analyze").raise_for_status()
            job = wait_for(
                lambda: client.get(f"/api/v1/jobs/{job['id']}").raise_for_status().json(),
                lambda j: j["status"] in {"ready", "coverage_failed", "failed", "cancelled"},
                timeout=1800,
                interval=5,
                what="job analysis",
            )
            report["job"] = {
                "status": job["status"],
                "role": job["role"],
                "company": job["company"],
            }
            if job["status"] != "ready":
                raise RuntimeError(f"analysis ended as {job['status']}")
            coverage = client.get(f"/api/v1/jobs/{job['id']}/coverage").raise_for_status().json()
            report["coverage"] = {
                "requirements": len(coverage),
                "labels": dict(Counter(r["match_label"] for r in coverage)),
                "required_labels": dict(
                    Counter(r["match_label"] for r in coverage if r["required"])
                ),
            }

        with Step(report, "generate_resume"):
            client.post(
                f"/api/v1/jobs/{job['id']}/generate",
                json={"mode": "conservative", "document_type": "resume"},
            ).raise_for_status()
            result: dict = {}
            for event, data in sse_events(
                client, job["id"], {"generation.completed", "generation.failed"}, 1800
            ):
                if event.startswith("generation."):
                    print(f"    {event}", flush=True)
                if event == "generation.failed":
                    raise RuntimeError(f"generation failed: {data}")
                result = data
            document = (
                client.get(f"/api/v1/documents/{result['document_id']}").raise_for_status().json()
            )
            claims = (
                client.get(f"/api/v1/documents/{document['id']}/claims").raise_for_status().json()
            )
            run_info = (
                client.get(f"/api/v1/generation-runs/{document['generation_run_id']}")
                .raise_for_status()
                .json()
            )
            report["generation"] = {
                "claims": len(claims),
                "verification": dict(Counter(c["verification_status"] for c in claims)),
                "claims_with_evidence": sum(1 for c in claims if c["evidence_id"]),
                "token_usage": run_info["token_usage"],
                "llm_latency_ms_total": round(run_info["latency_ms"]),
                "prompt_versions": run_info["prompt_versions"],
                "estimated_cost_usd_reported": run_info["estimated_cost"],
                "resume_bullets": sum(
                    len(e["bullets"]) for e in document["content_json"].get("experience", [])
                ),
                "skills_listed": len(document["content_json"].get("skills", [])),
            }

        with Step(report, "export_and_download"):
            exported = (
                client.post(f"/api/v1/documents/{document['id']}/export").raise_for_status().json()
            )
            link = (
                client.get(f"/api/v1/documents/{document['id']}/download", params={"format": "pdf"})
                .raise_for_status()
                .json()
            )
            # Fetched with no Authorization header, the way the browser follows it.
            pdf = httpx.get(link["url"], timeout=60)
            pdf.raise_for_status()
            assert pdf.content[:4] == b"%PDF", "download is not a PDF"
            report["export"] = {
                "page_count": exported["page_count"],
                "overflowed": exported["overflowed"],
                "pdf_bytes": len(pdf.content),
                "content_disposition": pdf.headers.get("content-disposition"),
            }
        report["ok"] = True
    except Exception as exc:
        report["ok"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAILED: {report['error']}", file=sys.stderr, flush=True)
    finally:
        if args.worker_log:
            report["llm_usage"] = llm_usage(args.worker_log, log_offset)
        if not args.keep and auth:
            deleted = httpx.delete(f"{args.api}/api/v1/auth/me", headers=auth, timeout=60)
            report["cleanup"] = f"user deleted ({deleted.status_code})"
        report["total_seconds"] = round(sum(report["stages"].values()), 1)
        text = json.dumps(report, indent=2)
        print(text)
        if args.out:
            args.out.write_text(text + "\n")
    sys.exit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
