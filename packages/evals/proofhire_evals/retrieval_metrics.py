"""Retrieval evaluation metrics (PRD §26.2): Recall@K, MRR, nDCG@K.

Pure functions over ranked ID lists and relevance judgments — no DB, no LLM,
so they run in CI without any live infrastructure. Seeded here in Phase 4
against a handful of hand-checked cases; grown into the full labeled benchmark
in Phase 9 once there's enough real evidence/JD data to label against.
"""

import math


def recall_at_k(relevant_ids: set[str], ranked_ids: list[str], k: int) -> float:
    """Fraction of all relevant items that appear in the top K ranked results.
    Returns 1.0 if there are no relevant items at all (vacuously satisfied —
    there's nothing to have missed)."""
    if not relevant_ids:
        return 1.0
    top_k = set(ranked_ids[:k])
    found = len(relevant_ids & top_k)
    return found / len(relevant_ids)


def mean_reciprocal_rank(relevant_ids: set[str], ranked_ids: list[str]) -> float:
    """Reciprocal of the rank (1-indexed) of the first relevant item. 0.0 if no
    relevant item appears anywhere in the ranked list."""
    for i, item_id in enumerate(ranked_ids, start=1):
        if item_id in relevant_ids:
            return 1.0 / i
    return 0.0


def ndcg_at_k(relevance_grades: dict[str, float], ranked_ids: list[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain over the top K results.
    relevance_grades maps item id -> graded relevance (0 = irrelevant, higher =
    more relevant); items not present are treated as 0."""
    top_k = ranked_ids[:k]

    def dcg(ids: list[str]) -> float:
        return sum(
            relevance_grades.get(item_id, 0.0) / math.log2(rank + 1)
            for rank, item_id in enumerate(ids, start=1)
        )

    actual_dcg = dcg(top_k)
    ideal_order = sorted(relevance_grades, key=lambda i: relevance_grades[i], reverse=True)[:k]
    ideal_dcg = dcg(ideal_order)

    if ideal_dcg == 0:
        return 1.0 if actual_dcg == 0 else 0.0
    return actual_dcg / ideal_dcg
