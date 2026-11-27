"""Retrieval component benchmark on public, human-annotated job-ad data (E1).

Task: for each job-ad sentence, rank the ESCO skill taxonomy (13.9K skills).
The relevant skills are the ones human annotators assigned to the sentence:
TECH and HOUSE are SkillSpan sentences with span-level ESCO labels (Decorte et
al., RecSys-in-HR 2022); TECHWOLF has sentence-level labels (Decorte et al.,
2023). CC BY 4.0; ESCO (c) European Union, reused with attribution.

A proxy for ProofHire's retrieval step — job-requirement language matched
against short, skill-level evidence text — run through the same machinery the
product uses:

  lexical_and    Postgres full text as hybrid_search ran it until this
                 benchmark: plainto_tsquery (every term must match), ts_rank_cd
  lexical_or     the same ranking, any term may match: hybrid_search since
  hash_fallback  SHA-256 pseudo-embeddings: what every deployment without an
                 OpenAI key silently used before ADR-0018
  dense          bge-small-en-v1.5 via ONNX, the production embedding model
  dense_instr    the same with the BGE query instruction on queries
  hybrid_prod    hybrid_search's fusion as it was: top-50 per signal, weighted
                 sum with the production weights, lexical_and + dense
  hybrid_or      the same fusion with lexical_or: hybrid_search now
  hybrid_or_instr  hybrid_or with the query instruction
  hybrid_or_rrf  reciprocal-rank fusion (k=60) of lexical_or and dense

Metrics per query (binary relevance): Recall@5, Recall@10, MRR (top 100),
nDCG@5; reported per dataset and pooled, with 95% bootstrap confidence
intervals (1,000 resamples over queries) on the pooled values.

Measures retrieval, not generation, and a proxy corpus, not ProofHire's own
evidence: see docs/product/metrics/retrieval-eval.md for what that does and
doesn't license.

    python apps/worker/scripts/eval_skill_retrieval.py --out docs/product/metrics
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
import platform
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np
from proofhire_api.repositories.evidence import (
    _LEXICAL_TSQUERY,
    CANDIDATES_PER_SIGNAL,
    LEXICAL_WEIGHT,
    VECTOR_WEIGHT,
)
from proofhire_evals.retrieval_metrics import mean_reciprocal_rank, ndcg_at_k, recall_at_k
from sqlalchemy import text

from proofhire_worker.db import engine
from proofhire_worker.intelligence.embeddings import LocalEmbeddingProvider

HF = "https://huggingface.co/datasets/TechWolf"
DATASETS = {
    "tech": f"{HF}/skill-extraction-tech/resolve/5f0cb05df03cd1cd5048ff1d64639bf9bd4cb36f/test.csv",
    "house": f"{HF}/skill-extraction-house/resolve/dcb313cad615a8f5148ef5addc01ef090fc9f295/test.csv",
    "techwolf": (
        f"{HF}/skill-extraction-techwolf/resolve/ed83e50ff6bc7e44008e98a82f6143ddaf59a255/test.csv"
    ),
}
ESCO_SKILLS = (
    "https://raw.githubusercontent.com/jensjorisdecorte/Skill-Extraction-benchmark/"
    "19305c85e35a74fb2a5128d8ee3798b06470b596/data/skills_en_label.txt"
)
NOT_A_LABEL = {"", "LABEL NOT PRESENT", "UNDERSPECIFIED"}
CACHE = Path.home() / ".cache" / "proofhire" / "evals"
TOP = 100
RRF_K = 60
BOOTSTRAP = 1000


def fetch(url: str) -> tuple[bytes, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not path.exists():
        path.write_bytes(
            httpx.get(url, follow_redirects=True, timeout=60).raise_for_status().content
        )
    data = path.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


def load_gold(raw: bytes, label_ids: dict[str, int]) -> tuple[list[tuple[str, set[int]]], dict]:
    gold: dict[str, set[str]] = defaultdict(set)
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        label = (row.get("label") or "").strip()
        if label not in NOT_A_LABEL:
            gold[row["sentence"].strip()].add(label)
    queries, unknown = [], 0
    for sentence, labels in gold.items():
        known = {label_ids[label] for label in labels if label in label_ids}
        unknown += len(labels) - len(known)
        if known:
            queries.append((sentence, known))
    return queries, {
        "sentences_with_labels": len(gold),
        "queries": len(queries),
        "labels_not_in_taxonomy": unknown,
    }


def pre_adr0018_hash(texts: list[str]) -> np.ndarray:
    """The old mock provider, byte for byte: SHA-256 cycled to 1536 floats in [0, 1]."""
    out = np.empty((len(texts), 1536), dtype=np.float32)
    for i, t in enumerate(texts):
        digest = hashlib.sha256(t.encode("utf-8")).digest()
        out[i] = [digest[j % len(digest)] / 255.0 for j in range(1536)]
    return out / np.linalg.norm(out, axis=1, keepdims=True)


def top_k(scores: np.ndarray, k: int = TOP) -> list[list[int]]:
    idx = np.argpartition(-scores, k, axis=1)[:, :k]
    order = np.take_along_axis(scores, idx, axis=1).argsort(axis=1)[:, ::-1]
    return np.take_along_axis(idx, order, axis=1).tolist()


async def embed(provider: LocalEmbeddingProvider, texts: list[str], input_type: str) -> np.ndarray:
    vectors = np.asarray(await provider.embed(texts, input_type=input_type), dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def _tsquery(mode: str) -> str:
    """The pre-2026-09-28 hybrid_search query (AND of every lexeme), or the
    production one (the same lexemes OR'd), imported so the two can't drift."""
    return "plainto_tsquery('english', :text)" if mode == "and" else _LEXICAL_TSQUERY


async def lexical(conn, sentence: str, mode: str, k: int) -> list[tuple[int, float]]:
    rows = await conn.execute(
        text(
            "SELECT id, LEAST(1.0, ts_rank_cd(tsv, query.q)) AS s "
            f"FROM bench_skills, (SELECT {_tsquery(mode)} AS q) AS query "
            "WHERE tsv @@ query.q ORDER BY s DESC, id LIMIT :k"
        ),
        {"text": sentence, "k": k},
    )
    return [(r.id, float(r.s)) for r in rows]


async def lexical_scores(conn, sentence: str, mode: str, ids: list[int]) -> dict[int, float]:
    rows = await conn.execute(
        text(
            "SELECT id, LEAST(1.0, COALESCE(ts_rank_cd(tsv, query.q), 0)) AS s "
            f"FROM bench_skills, (SELECT {_tsquery(mode)} AS q) AS query WHERE id = ANY(:ids)"
        ),
        {"text": sentence, "ids": ids},
    )
    return {r.id: float(r.s) for r in rows}


def metrics(gold: set[int], ranked: list[int]) -> dict[str, float]:
    g = {str(i) for i in gold}
    r = [str(i) for i in ranked]
    return {
        "recall@5": recall_at_k(g, r, 5),
        "recall@10": recall_at_k(g, r, 10),
        "mrr": mean_reciprocal_rank(g, r),
        "ndcg@5": ndcg_at_k(dict.fromkeys(g, 1.0), r, 5),
    }


# Decisions this benchmark informs, each a paired comparison over the same
# queries: (candidate, baseline).
COMPARISONS = [
    ("hybrid_or", "hybrid_prod"),  # OR semantics in the lexical branch
    ("hybrid_or_instr", "hybrid_prod"),  # ... plus the BGE query instruction
    ("hybrid_or_instr", "hybrid_or"),
    ("dense_instr", "dense"),  # the instruction on its own
    ("hybrid_or_rrf", "hybrid_or"),  # RRF instead of the weighted sum (ADR-0006)
    ("dense", "hash_fallback"),  # ADR-0018: real embeddings vs the old fallback
]


def paired_difference(a: list[float], b: list[float], rng: np.random.Generator) -> dict:
    """Mean per-query difference a - b with a 95% bootstrap CI; resampling
    queries keeps each query's pair together, which unpaired CIs ignore."""
    diff = np.asarray(a) - np.asarray(b)
    boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(BOOTSTRAP)]
    lo, hi = np.percentile(boots, 2.5), np.percentile(boots, 97.5)
    return {
        "mean": round(float(diff.mean()), 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
        "excludes_zero": bool(lo > 0 or hi < 0),
    }


def fuse(candidates: list[int], lex: dict[int, float], vec: np.ndarray) -> list[int]:
    """hybrid_search's weighted sum over the candidate union."""
    return sorted(
        candidates,
        key=lambda c: -(LEXICAL_WEIGHT * lex.get(c, 0.0) + VECTOR_WEIGHT * max(0.0, float(vec[c]))),
    )


def summarize(per_query: list[dict[str, float]], rng: np.random.Generator) -> dict:
    out = {}
    for metric in ("recall@5", "recall@10", "mrr", "ndcg@5"):
        values = np.array([q[metric] for q in per_query])
        boots = [values[rng.integers(0, len(values), len(values))].mean() for _ in range(BOOTSTRAP)]
        out[metric] = {
            "mean": round(float(values.mean()), 4),
            "ci95": [
                round(float(np.percentile(boots, 2.5)), 4),
                round(float(np.percentile(boots, 97.5)), 4),
            ],
        }
    return out


async def main(out_dir: Path) -> None:
    started = time.perf_counter()
    raw_skills, skills_sha = fetch(ESCO_SKILLS)
    skills = list(
        dict.fromkeys(s.strip() for s in raw_skills.decode("utf-8").splitlines() if s.strip())
    )
    label_ids = {label: i for i, label in enumerate(skills)}

    queries: list[tuple[str, str, set[int]]] = []
    data_report = {}
    for name, url in DATASETS.items():
        raw, sha = fetch(url)
        rows, stats = load_gold(raw, label_ids)
        queries += [(name, sentence, gold) for sentence, gold in rows]
        data_report[name] = {"url": url, "sha256": sha, **stats}
    sentences = [q[1] for q in queries]
    print(f"{len(skills)} ESCO skills, {len(queries)} labelled queries", flush=True)

    plain = LocalEmbeddingProvider(query_instruction=False)
    instructed = LocalEmbeddingProvider(query_instruction=True)
    doc_cache = CACHE / f"esco-{skills_sha[:16]}-{plain.model_id.replace('/', '_')}.npy"
    if doc_cache.exists():
        docs = np.load(doc_cache)
    else:
        t0 = time.perf_counter()
        docs = await embed(plain, skills, "document")
        np.save(doc_cache, docs)
        print(f"embedded {len(skills)} skills in {time.perf_counter() - t0:.0f}s", flush=True)
    dense_scores = (await embed(plain, sentences, "query")) @ docs.T
    instr_scores = (await embed(instructed, sentences, "query")) @ docs.T
    hash_scores = pre_adr0018_hash(sentences) @ pre_adr0018_hash(skills).T

    rankings: dict[str, list[list[int]]] = {
        "dense": top_k(dense_scores),
        "dense_instr": top_k(instr_scores),
        "hash_fallback": top_k(hash_scores),
        "lexical_and": [],
        "lexical_or": [],
        "hybrid_prod": [],
        "hybrid_or": [],
        "hybrid_or_instr": [],
        "hybrid_or_rrf": [],
    }

    async with engine.connect() as conn:
        await conn.execute(
            text(
                "CREATE TEMP TABLE bench_skills (id int PRIMARY KEY, label text NOT NULL, tsv tsvector)"
            )
        )
        await conn.execute(
            text("INSERT INTO bench_skills (id, label) VALUES (:id, :label)"),
            [{"id": i, "label": s} for i, s in enumerate(skills)],
        )
        await conn.execute(text("UPDATE bench_skills SET tsv = to_tsvector('english', label)"))
        await conn.execute(text("CREATE INDEX ON bench_skills USING gin (tsv)"))
        await conn.execute(text("ANALYZE bench_skills"))
        for qi, sentence in enumerate(sentences):
            and_hits = await lexical(conn, sentence, "and", TOP)
            or_hits = await lexical(conn, sentence, "or", TOP)
            rankings["lexical_and"].append([i for i, _ in and_hits])
            rankings["lexical_or"].append([i for i, _ in or_hits])
            # hybrid_search: top-K per signal, then the weighted sum over the union.
            variants = (
                ("hybrid_prod", "and", and_hits, "dense", dense_scores),
                ("hybrid_or", "or", or_hits, "dense", dense_scores),
                ("hybrid_or_instr", "or", or_hits, "dense_instr", instr_scores),
            )
            for name, mode, hits, dense_name, vec_scores in variants:
                candidates = list(
                    dict.fromkeys(
                        [i for i, _ in hits[:CANDIDATES_PER_SIGNAL]]
                        + rankings[dense_name][qi][:CANDIDATES_PER_SIGNAL]
                    )
                )
                lex = await lexical_scores(conn, sentence, mode, candidates)
                rankings[name].append(fuse(candidates, lex, vec_scores[qi]))
            rrf: dict[int, float] = defaultdict(float)
            for ranked in ([i for i, _ in or_hits], rankings["dense"][qi]):
                for rank, doc in enumerate(ranked, start=1):
                    rrf[doc] += 1.0 / (RRF_K + rank)
            rankings["hybrid_or_rrf"].append(sorted(rrf, key=lambda d: -rrf[d])[:TOP])
            if (qi + 1) % 250 == 0:
                print(f"lexical/hybrid: {qi + 1}/{len(sentences)}", flush=True)
        await conn.rollback()

    rng = np.random.default_rng(20260928)
    results: dict = {}
    per_method: dict[str, list[dict[str, float]]] = {}
    for method, ranked_lists in rankings.items():
        per_query = [metrics(gold, ranked) for (_, _, gold), ranked in zip(queries, ranked_lists)]
        per_method[method] = per_query
        results[method] = {"pooled": summarize(per_query, rng)}
        for name in DATASETS:
            subset = [m for (ds, _, _), m in zip(queries, per_query) if ds == name]
            results[method][name] = {
                k: round(float(np.mean([m[k] for m in subset])), 4) for k in subset[0]
            }
        # Where AND semantics finds nothing at all, it can't rank anything.
        results[method]["queries_with_no_results"] = sum(1 for r in ranked_lists if not r)

    comparisons = {
        f"{a} - {b}": {
            metric: paired_difference(
                [q[metric] for q in per_method[a]], [q[metric] for q in per_method[b]], rng
            )
            for metric in ("mrr", "recall@5")
        }
        for a, b in COMPARISONS
    }

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "rank ESCO skills for a job-ad sentence; relevant = human-assigned labels",
        "taxonomy": {"url": ESCO_SKILLS, "sha256": skills_sha, "skills": len(skills)},
        "datasets": data_report,
        "queries": len(queries),
        "embedding_model": plain.model_id,
        "fusion_weights": {"lexical": LEXICAL_WEIGHT, "vector": VECTOR_WEIGHT},
        "candidates_per_signal": CANDIDATES_PER_SIGNAL,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "seconds": round(time.perf_counter() - started, 1),
        "results": results,
        "paired_comparisons": comparisons,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "retrieval-eval.json").write_text(json.dumps(report, indent=2) + "\n")

    order = sorted(results, key=lambda m: -results[m]["pooled"]["mrr"]["mean"])
    lines = [
        "| Method | Recall@5 | Recall@10 | MRR | nDCG@5 | Queries with no results |",
        "|---|---|---|---|---|---|",
    ]
    for m in order:
        p = results[m]["pooled"]

        def cell(key: str, p=p) -> str:
            lo, hi = p[key]["ci95"]
            return f"{p[key]['mean']:.3f} [{lo:.3f}, {hi:.3f}]"

        lines.append(
            f"| {m} | {cell('recall@5')} | {cell('recall@10')} | {cell('mrr')} "
            f"| {cell('ndcg@5')} | {results[m]['queries_with_no_results']} |"
        )
    lines += [
        "",
        "| Paired comparison (same queries) | ΔMRR [95% CI] | ΔRecall@5 [95% CI] |",
        "|---|---|---|",
    ]
    for name, c in comparisons.items():

        def delta(metric: str, c=c) -> str:
            d = c[metric]
            mark = "" if d["excludes_zero"] else " (n.s.)"
            return f"{d['mean']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]{mark}"

        lines.append(f"| {name} | {delta('mrr')} | {delta('recall@5')} |")
    table = "\n".join(lines)
    (out_dir / "retrieval-eval-table.md").write_text(table + "\n")
    print(table)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("docs/product/metrics"))
    asyncio.run(main(ap.parse_args().out))
