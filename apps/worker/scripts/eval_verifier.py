"""Claim verification against planted hallucinations (E3).

The product's core promise: a claim the evidence doesn't support is caught and
removed before export. This measures how often that holds, with ground truth
by construction rather than by judgement:

- Evidence: the production extraction prompt and model run over files of this
  repository (cached after the first run, so reruns spend no tokens).
- True bullets: an evidence item's normalized claim, verbatim — supported by
  construction — plus an employment control that matches the confirmed
  profile fact exactly.
- Traps: true bullets with one planted fabrication each:
    metric       a number the evidence never states
    technology   a technology absent from all of the evidence
    scope        inflated ownership ("led a team of 6")
    employment   a title and start date contradicting the confirmed fact
- Each document (4 true + 4 traps, shuffled) goes through the production
  verification path: the claim_verify prompt on the production model, then
  the deterministic fact guard (generation._run_claim_verification).

A bullet counts as caught when any claim extracted from it ends UNSUPPORTED
or CONTRADICTORY — exactly the condition under which generation strips it.
Reported: catch rate per trap type, the false-positive rate on true bullets,
and the same with the LLM's own status alone (no guard), with 95% Wilson
intervals.

    python apps/worker/scripts/eval_verifier.py --documents 20 --out docs/product/metrics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import random
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from proofhire_contracts import ClaimVerificationStatus
from proofhire_prompts.evidence_extract_v1 import SYSTEM_PROMPT, build_user_message

from proofhire_worker.intelligence.evidence_extraction import _group_files
from proofhire_worker.intelligence.generation import CLAIM_VERIFY_VERSION, _run_claim_verification
from proofhire_worker.intelligence.llm_provider import Message
from proofhire_worker.intelligence.model_selection import config_for, provider_name
from proofhire_worker.intelligence.provider_factory import get_provider
from proofhire_worker.intelligence.schemas import EvidenceExtractionOutput

ROOT = Path(__file__).resolve().parents[3]
SOURCE_FILES = [
    "apps/api/proofhire_api/services/object_storage.py",
    "apps/api/proofhire_api/repositories/evidence.py",
    "apps/worker/proofhire_worker/intelligence/coverage.py",
    "apps/worker/proofhire_worker/intelligence/embeddings.py",
    "apps/worker/proofhire_worker/intelligence/retry.py",
    "apps/worker/proofhire_worker/intelligence/providers/groq_provider.py",
    "apps/worker/proofhire_worker/ingestion/sync.py",
    "apps/api/proofhire_api/routers/auth.py",
]
CACHE = Path.home() / ".cache" / "proofhire" / "evals" / "verifier-evidence.json"
REPOSITORY = "sadad54/ResumeGitProject"
FACT = {
    "employer": "Acme Analytics",
    "title": "Backend Engineer",
    "start_date": "2021",
    "end_date": "Present",
}
TECHNOLOGIES = [
    "Kubernetes",
    "Apache Kafka",
    "Terraform",
    "GraphQL",
    "Apache Spark",
    "Elasticsearch",
]
CAUGHT = {ClaimVerificationStatus.UNSUPPORTED, ClaimVerificationStatus.CONTRADICTORY}


def wilson(k: int, n: int) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    z, p = 1.96, k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


async def evidence_set(provider) -> list[dict]:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    files = [(path, (ROOT / path).read_text()) for path in SOURCE_FILES]
    items: list[dict] = []
    for group in _group_files(files):
        result = await provider.structured_generate(
            task="evidence_extract",
            messages=[
                Message(role="system", content=SYSTEM_PROMPT),
                Message(role="user", content=build_user_message(REPOSITORY, group)),
            ],
            schema=EvidenceExtractionOutput,
            model_config=config_for("evidence_extract"),
        )
        items += [
            {"title": e.title, "normalized_claim": e.normalized_claim, "description": e.description}
            for e in result.value.evidence
        ]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(items, indent=2))
    return items


def claim_text(bullet: str) -> str:
    return bullet.rstrip(". ")


def make_traps(bullet: str, corpus: str, rng: random.Random) -> dict[str, str]:
    body = claim_text(bullet)
    lowered = body[0].lower() + body[1:]
    technology = next(
        t for t in rng.sample(TECHNOLOGIES, len(TECHNOLOGIES)) if t.lower() not in corpus
    )
    return {
        "metric": f"{body}, cutting p95 latency by 43%.",
        "technology": f"{body}, deployed on {technology}.",
        "scope": f"Led a team of 6 engineers that {lowered[0].lower() + lowered[1:]}.",
        "employment": f"As Principal Engineer at {FACT['employer']} since 2016, {lowered}.",
    }


async def main(documents: int, out_dir: Path, seed: int) -> None:
    started = time.perf_counter()
    provider = get_provider()
    evidence = await evidence_set(provider)
    corpus = " ".join(
        f"{e['title']} {e['normalized_claim']} {e['description']}" for e in evidence
    ).lower()
    assert "43%" not in corpus and "team of 6" not in corpus
    repo_id = uuid.uuid4()
    evidence_items = [
        SimpleNamespace(id=uuid.uuid4(), repository_id=repo_id, **e) for e in evidence
    ]
    facts = [SimpleNamespace(id=uuid.uuid4(), type="employment", value_json=FACT)]
    rng = random.Random(seed)

    rows: list[dict] = []
    usage: list = []
    errored: list[dict] = []
    for d in range(documents):
        chosen = rng.sample(evidence, 8)  # every bullet from a distinct evidence item
        units = [("true_evidence", e["normalized_claim"]) for e in chosen[:3]]
        units.append(
            (
                "true_employment",
                f"As {FACT['title']} at {FACT['employer']} since {FACT['start_date']}, "
                f"{claim_text(chosen[3]['normalized_claim'])[0].lower()}"
                f"{claim_text(chosen[3]['normalized_claim'])[1:]}.",
            )
        )
        for kind, source in zip(("metric", "technology", "scope", "employment"), chosen[4:]):
            units.append(
                (f"trap_{kind}", make_traps(source["normalized_claim"], corpus, rng)[kind])
            )
        rng.shuffle(units)
        document_units = [(i, text) for i, (_, text) in enumerate(units)]
        t0 = time.perf_counter()
        try:
            finalized, _result = await _run_claim_verification(
                provider,
                document_units,
                facts,
                evidence_items,
                f"eval-{d}",
                usage,
                {repo_id: REPOSITORY},
            )
        except Exception as exc:  # a spent daily quota, say: keep what was measured
            errored.append({"document": d, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            print(f"document {d + 1}/{documents}: FAILED {errored[-1]['error']}", flush=True)
            continue
        seconds = time.perf_counter() - t0
        for i, (kind, text) in enumerate(units):
            claims = [(c, s) for c, s, _ in finalized if c.bullet_index == i]
            rows.append(
                {
                    "document": d,
                    "kind": kind,
                    "text": text,
                    "claims": len(claims),
                    "caught": any(s in CAUGHT for _, s in claims),
                    "caught_llm_only": any(
                        c.status.strip().lower() in {"unsupported", "contradictory"}
                        for c, _ in claims
                    ),
                    "final_statuses": sorted({s.value for _, s in claims}),
                }
            )
        print(f"document {d + 1}/{documents}: {seconds:.1f}s", flush=True)

    kinds = sorted({r["kind"] for r in rows})
    by_kind = {}
    for kind in kinds:
        subset = [r for r in rows if r["kind"] == kind]
        k, k_llm = sum(r["caught"] for r in subset), sum(r["caught_llm_only"] for r in subset)
        by_kind[kind] = {
            "n": len(subset),
            # For a trap, "caught" is the goal; for a true bullet it's a false positive.
            "caught_rate": round(k / len(subset), 3),
            "caught_ci95": wilson(k, len(subset)),
            "caught_rate_llm_only": round(k_llm / len(subset), 3),
            "no_claim_extracted": sum(1 for r in subset if r["claims"] == 0),
        }
    traps = [r for r in rows if r["kind"].startswith("trap_")]
    trues = [r for r in rows if r["kind"].startswith("true_")]
    summary = {
        "trap_catch_rate": round(sum(r["caught"] for r in traps) / len(traps), 3),
        "trap_catch_ci95": wilson(sum(r["caught"] for r in traps), len(traps)),
        "trap_catch_rate_llm_only": round(sum(r["caught_llm_only"] for r in traps) / len(traps), 3),
        "false_positive_rate": round(sum(r["caught"] for r in trues) / len(trues), 3),
        "false_positive_ci95": wilson(sum(r["caught"] for r in trues), len(trues)),
        "false_positive_rate_llm_only": round(
            sum(r["caught_llm_only"] for r in trues) / len(trues), 3
        ),
    }
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": provider_name(),
        "verifier_model": config_for("claim_verify").model,
        "verifier_prompt": CLAIM_VERIFY_VERSION,
        "extraction_model": config_for("evidence_extract").model,
        "evidence_items": len(evidence),
        "documents": documents,
        "documents_errored": errored,
        "bullets": len(rows),
        "seed": seed,
        "summary": summary,
        "by_kind": by_kind,
        "tokens": {
            "input": sum(u.input_tokens for u in usage),
            "output": sum(u.output_tokens for u in usage),
            "calls": len(usage),
        },
        "verify_latency_ms_mean": round(sum(u.latency_ms for u in usage) / max(1, len(usage))),
        "seconds": round(time.perf_counter() - started, 1),
        "environment": {"python": platform.python_version()},
        "evidence": evidence,
        "rows": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    # One file per verifier prompt version, so a change is measured against
    # the committed result of the version before it.
    name = f"verifier-eval-{CLAIM_VERIFY_VERSION.split(':')[1]}"
    (out_dir / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "| Bullet kind | n | Caught (LLM + guard) [95% CI] | Caught (LLM alone) | No claim extracted |",
        "|---|---|---|---|---|",
    ]
    for kind, v in by_kind.items():
        lo, hi = v["caught_ci95"]
        lines.append(
            f"| {kind} | {v['n']} | {v['caught_rate']:.2f} [{lo:.2f}, {hi:.2f}] "
            f"| {v['caught_rate_llm_only']:.2f} | {v['no_claim_extracted']} |"
        )
    print("\n".join(lines))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--documents", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--out", type=Path, default=Path("docs/product/metrics"))
    args = ap.parse_args()
    asyncio.run(main(args.documents, args.out, args.seed))
