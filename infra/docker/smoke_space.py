"""Smoke-test a running ProofHire Space container through its public API.

CI builds the exact image the Space builds (infra/docker/Dockerfile.space),
boots it with production settings against a real Postgres, and runs this.
Each check exercises machinery that unit tests can't: the entrypoint's
migrations, the in-container Redis and Dramatiq worker (a job round-trips
API -> queue -> worker -> database), Chromium rendering a real template to PDF
as the Space's uid-1000 user, and the embedding model baked into the image
(loaded with the network forbidden). The LLM provider is the mock: model
calls are covered by scripts/e2e_live.py against the real provider.

    python infra/docker/smoke_space.py --api http://127.0.0.1:7860 --container space
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime

import httpx

RESULTS: list[bool] = []


def check(name: str, ok: bool, detail: object = "") -> bool:
    RESULTS.append(bool(ok))
    print(
        f"{'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail not in ("", None) else ""),
        flush=True,
    )
    return bool(ok)


def in_container(container: str, code: str, env: dict[str, str] | None = None) -> dict:
    """Run Python inside the container as its own user; the code prints one JSON line."""
    flags = [arg for k, v in (env or {}).items() for arg in ("-e", f"{k}={v}")]
    out = subprocess.run(
        ["docker", "exec", *flags, container, "python", "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if out.returncode != 0:
        return {"error": out.stderr.strip()[-600:]}
    return json.loads(out.stdout.strip().splitlines()[-1])


PDF_CODE = """
import asyncio, json
from proofhire_worker.render.templates import render_resume_html
from proofhire_worker.render.pdf_renderer import render_html_to_pdf
from proofhire_worker.render.parse_back import validate_parse_back
html = render_resume_html({"summary": "Smoke test summary line.", "skills": ["Python"],
    "experience": [{"employer": "Smoke Co", "title": "Engineer", "start_date": "2024",
                    "end_date": "Present", "bullets": ["Rendered in the production image."]}]},
    "smoke@example.org")
pdf = asyncio.run(render_html_to_pdf(html))
expected = ["Smoke test summary line.", "Rendered in the production image."]
ok, missing = validate_parse_back(pdf, expected)
print(json.dumps({"bytes": len(pdf), "pdf": pdf[:4] == b"%PDF", "parse_back": ok,
                  "missing": missing}))
"""

EMBED_CODE = """
import asyncio, json
from proofhire_worker.intelligence.embeddings import LocalEmbeddingProvider
[v] = asyncio.run(LocalEmbeddingProvider().embed(["FastAPI service with pgvector retrieval"]))
print(json.dumps({"dim": len(v)}))
"""

PROCESSES_CODE = """
import json, pathlib
cmds = [p.read_bytes().replace(b"\\0", b" ").decode(errors="replace")
        for p in pathlib.Path("/proc").glob("[0-9]*/cmdline") if p.exists()]
print(json.dumps({"worker": any("dramatiq proofhire_worker.tasks" in c for c in cmds),
                  "redis": any("redis-server" in c for c in cmds)}))
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--api", default="http://127.0.0.1:7860")
    ap.add_argument(
        "--container", default=None, help="docker container name, for the in-container checks"
    )
    args = ap.parse_args()
    api = httpx.Client(base_url=args.api, timeout=30)

    ready = api.get("/ready")
    check(
        "ready: postgres and redis reachable from the API",
        ready.status_code == 200
        and ready.json().get("postgres") == "ok"
        and ready.json().get("redis") == "ok",
        ready.text,
    )

    email = f"smoke-{uuid.uuid4().hex[:10]}@example.org"
    signup = api.post("/api/v1/auth/signup", json={"email": email, "password": uuid.uuid4().hex})
    if not check(
        "signup", signup.status_code == 201 or signup.status_code == 200, signup.status_code
    ):
        return 1
    auth = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    me = api.get("/api/v1/auth/me", headers=auth)
    check("/auth/me", me.status_code == 200 and me.json().get("is_demo") is False, me.status_code)
    overview = api.get("/api/v1/me/overview", headers=auth)
    check(
        "/me/overview",
        overview.status_code == 200 and overview.json()["repositories"]["total"] == 0,
        overview.status_code,
    )

    # API -> Redis -> Dramatiq worker -> Postgres. With the mock provider the
    # analysis has no requirements, so the job settles straight to ready.
    job = api.post(
        "/api/v1/jobs/capture",
        headers=auth,
        json={
            "selected_text": "Backend engineer: Python, FastAPI, PostgreSQL. " * 3,
            "captured_at": datetime.now(UTC).isoformat(),
        },
    ).json()
    api.post(f"/api/v1/jobs/{job['id']}/analyze", headers=auth).raise_for_status()
    status, deadline = None, time.monotonic() + 120
    while time.monotonic() < deadline:
        status = api.get(f"/api/v1/jobs/{job['id']}", headers=auth).json()["status"]
        if status in {"ready", "coverage_failed", "failed", "cancelled"}:
            break
        time.sleep(2)
    check("queue round trip: the worker analyzed a job", status == "ready", status)

    demo = api.post("/api/v1/demo/session")
    if check("demo session", demo.status_code == 200, demo.status_code):
        demo_auth = {"Authorization": f"Bearer {demo.json()['access_token']}"}
        demo_me = api.get("/api/v1/auth/me", headers=demo_auth).json()
        refused = api.post(
            "/api/v1/jobs/capture", headers=demo_auth, json={"selected_text": "x" * 60}
        )
        check(
            "demo account is read-only",
            demo_me.get("is_demo") is True and refused.status_code == 403,
            refused.status_code,
        )

    deleted = api.delete("/api/v1/auth/me", headers=auth)
    after = api.get("/api/v1/auth/me", headers=auth)
    check(
        "account deletion",
        deleted.status_code == 204 and after.status_code == 401,
        (deleted.status_code, after.status_code),
    )

    if args.container:
        processes = in_container(args.container, PROCESSES_CODE)
        check(
            "worker and redis running",
            processes.get("worker") and processes.get("redis"),
            processes,
        )
        pdf = in_container(args.container, PDF_CODE)
        check(
            "chromium renders a resume template; its text parses back out of the PDF",
            pdf.get("pdf") and pdf.get("parse_back"),
            pdf,
        )
        embed = in_container(
            args.container, EMBED_CODE, env={"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        )
        check("embedding model is baked in (loaded offline, 384-d)", embed.get("dim") == 384, embed)

    failed = RESULTS.count(False)
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
