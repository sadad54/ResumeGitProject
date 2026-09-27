"""Resource cost of the local embedding model (ADR-0018): memory and speed.

Measures, in one fresh process: RSS before/after importing the worker's
embedding module, after loading the ONNX model, and after embedding a batch;
model load time; per-text latency in a warm batch. Linux only (/proc).

    python apps/worker/scripts/measure_embedding_model.py [--out docs/product/metrics/embedding-model.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path


def rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024, 1)
    raise RuntimeError("VmRSS not found (Linux /proc required)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    baseline = rss_mb()
    from proofhire_worker.intelligence.embeddings import LocalEmbeddingProvider

    after_import = rss_mb()
    provider = LocalEmbeddingProvider()
    t0 = time.perf_counter()
    provider._model()
    load_seconds = time.perf_counter() - t0
    after_load = rss_mb()

    texts = [
        f"Implemented feature {i}: a FastAPI endpoint backed by Postgres with Redis caching."
        for i in range(args.batch)
    ]
    asyncio.run(provider.embed(texts[:8]))  # warm the session
    t0 = time.perf_counter()
    asyncio.run(provider.embed(texts))
    batch_seconds = time.perf_counter() - t0
    after_embed = rss_mb()

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": provider.model_id,
        "dimension": provider.dimension,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "rss_mb": {
            "process_baseline": baseline,
            "after_import": after_import,
            "after_model_load": after_load,
            "after_embedding_batch": after_embed,
        },
        "model_load_delta_mb": round(after_load - after_import, 1),
        "peak_delta_with_inference_mb": round(after_embed - after_import, 1),
        "model_load_seconds_from_cache": round(load_seconds, 2),
        "batch_size": args.batch,
        "ms_per_text_warm_batch": round(batch_seconds / args.batch * 1000, 2),
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
