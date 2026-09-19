"""Score reviewed benchmark runs. Missing measurements fail release gates.

This CLI never calls providers: input run records must come from actual pipeline
runs and independent claim/fact adjudication. See packages/evals/README.md.
"""

import argparse
import json
import math
from pathlib import Path
from statistics import mean

from .retrieval_metrics import mean_reciprocal_rank, ndcg_at_k, recall_at_k

FAMILIES = {"swe", "frontend", "backend", "full-stack", "ai-ml", "data", "mlops-devops"}


def load_jsonl(path):
    rows = [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs are not allowed")
    return rows


def f1(expected, actual):
    gold, predicted = set(expected), set(actual)
    if not gold and not predicted:
        return 1.0
    return 2 * len(gold & predicted) / (len(gold) + len(predicted))


def finite_nonnegative(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def score(dataset, runs, *, release=False):
    if not dataset or not runs:
        raise ValueError("Dataset and run records must be nonempty")
    gold = {case["id"]: case for case in dataset}
    if len(gold) != len(dataset) or len({r["id"] for r in runs}) != len(runs):
        raise ValueError("Duplicate case IDs are not allowed")
    if set(gold) != {r["id"] for r in runs}:
        raise ValueError(
            "Run IDs must exactly match dataset IDs (no cherry-picked subset)"
        )
    for case in dataset:
        if case.get("family") not in FAMILIES:
            raise ValueError("Every case must have a supported role family")
        if not isinstance(case.get("requirements"), list) or not case["requirements"]:
            raise ValueError("Each case needs labeled requirement IDs")
    extraction, recall, mrr, ndcg = [], [], [], []
    totals = {
        k: 0
        for k in [
            "claims",
            "unsupported_claims",
            "immutable_facts",
            "preserved_facts",
            "parse_back_attempts",
            "parse_back_successes",
            "secret_leaks",
            "input_tokens",
            "output_tokens",
            "cost_usd",
        ]
    }
    missing, latency = set(), []
    for run in runs:
        case = gold[run["id"]]
        if "requirements" not in run:
            missing.add("requirements")
        extraction.append(f1(case["requirements"], run.get("requirements", [])))
        ranked = run.get("ranked_evidence", {})
        for requirement, grades in case.get("evidence_matches", {}).items():
            if requirement not in ranked:
                missing.add("ranked_evidence")
            ids = ranked.get(requirement, [])
            if len(ids) != len(set(ids)):
                raise ValueError("Ranked evidence cannot contain duplicate IDs")
            relevant = {key for key, value in grades.items() if value > 0}
            recall.append(recall_at_k(relevant, ids, 5))
            mrr.append(mean_reciprocal_rank(relevant, ids))
            ndcg.append(ndcg_at_k(grades, ids, 5))
        for name in totals:
            value = run.get(name)
            if value is None:
                missing.add(name)
            elif not finite_nonnegative(value):
                raise ValueError(f"Invalid measurement: {name}")
            elif name != "cost_usd" and int(value) != value:
                raise ValueError(f"Count must be an integer: {name}")
            else:
                totals[name] += value
        for numerator, denominator in [
            ("unsupported_claims", "claims"),
            ("preserved_facts", "immutable_facts"),
            ("parse_back_successes", "parse_back_attempts"),
        ]:
            if run.get(numerator, 0) > run.get(denominator, 0):
                raise ValueError(f"{numerator} exceeds {denominator}")
        if finite_nonnegative(run.get("latency_ms")):
            latency.append(run["latency_ms"])
        else:
            missing.add("latency_ms")

    def ratio(a, b):
        return totals[a] / totals[b] if totals[b] else None

    metrics = {
        "requirement_f1": mean(extraction),
        "recall_at_5": mean(recall) if recall else None,
        "mrr": mean(mrr) if mrr else None,
        "ndcg_at_5": mean(ndcg) if ndcg else None,
        "unsupported_claim_rate": ratio("unsupported_claims", "claims"),
        "immutable_fact_preservation": ratio("preserved_facts", "immutable_facts"),
        "parse_back_success_rate": ratio("parse_back_successes", "parse_back_attempts"),
        "latency_ms_mean": mean(latency) if latency else None,
        "latency_ms_p95": sorted(latency)[math.ceil(len(latency) * 0.95) - 1]
        if latency
        else None,
        **totals,
    }
    reviewed = all(
        c.get("review", {}).get("status") == "human_reviewed"
        and c["review"].get("reviewer")
        for c in dataset
    )
    gates = {
        "requirement_f1": metrics["requirement_f1"] >= 0.90,
        "recall_at_5": metrics["recall_at_5"] is not None
        and metrics["recall_at_5"] >= 0.90,
        "unsupported_claim_rate": metrics["unsupported_claim_rate"] is not None
        and metrics["unsupported_claim_rate"] < 0.01,
        "immutable_facts": metrics["immutable_fact_preservation"] == 1,
        "parse_back": metrics["parse_back_success_rate"] is not None
        and metrics["parse_back_success_rate"] >= 0.99,
        "zero_secrets": "secret_leaks" not in missing and totals["secret_leaks"] == 0,
        "complete_measurements": not missing,
    }
    if release:
        gates.update(
            {
                "100_reviewed_jds": len(dataset) >= 100 and reviewed,
                "all_role_families": {c["family"] for c in dataset} == FAMILIES,
            }
        )
    return {
        "mode": "release" if release else "smoke",
        "cases": len(dataset),
        "human_reviewed": reviewed,
        "metrics": metrics,
        "missing_measurements": sorted(missing),
        "gates": gates,
        "passed": all(gates.values()),
    }


def measured_budget(runs, cases_per_provider):
    estimates = {}
    for provider in ("openai", "anthropic"):
        costs = [r.get("cost_usd") for r in runs if r.get("provider") == provider]
        if not costs or any(not finite_nonnegative(c) or c == 0 for c in costs):
            raise ValueError(
                f"Need nonzero measured {provider} costs before proposing a spend cap"
            )
        estimates[provider] = max(costs) * cases_per_provider
    return {
        "cases_per_provider": cases_per_provider,
        "provider_estimates_usd": estimates,
        "proposed_cap_usd": math.ceil(sum(estimates.values()) * 1.25 * 100) / 100,
        "method": "Maximum observed per-run cost per provider × cases × 1.25 safety margin. Not a provider-side spending limit.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("score")
    check.add_argument("--dataset", required=True)
    check.add_argument("--runs", required=True)
    check.add_argument("--release", action="store_true")
    check.add_argument("--output", required=True)
    budget = sub.add_parser("budget")
    budget.add_argument("--runs", required=True)
    budget.add_argument("--cases", type=int, default=100)
    args = parser.parse_args()
    try:
        runs = load_jsonl(args.runs)
        if args.command == "budget":
            if args.cases < 1:
                raise ValueError("cases must be positive")
            print(json.dumps(measured_budget(runs, args.cases), indent=2))
            return
        result = score(load_jsonl(args.dataset), runs, release=args.release)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"{result['mode']}: {result['cases']} cases — {'PASS' if result['passed'] else 'FAIL'}"
        )
        for name, passed in result["gates"].items():
            print(f"  {name}: {'PASS' if passed else 'FAIL'}")
        raise SystemExit(0 if result["passed"] else 1)
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
