import pytest

from proofhire_evals.retrieval_metrics import mean_reciprocal_rank, ndcg_at_k, recall_at_k


def test_recall_at_k_perfect():
    assert recall_at_k({"a", "b"}, ["a", "b", "c"], k=3) == 1.0


def test_recall_at_k_partial():
    assert recall_at_k({"a", "b"}, ["a", "x", "y"], k=3) == 0.5


def test_recall_at_k_respects_k_cutoff():
    assert recall_at_k({"a"}, ["x", "y", "a"], k=2) == 0.0
    assert recall_at_k({"a"}, ["x", "y", "a"], k=3) == 1.0


def test_recall_at_k_vacuous_when_nothing_relevant():
    assert recall_at_k(set(), ["a", "b"], k=5) == 1.0


def test_mrr_first_position():
    assert mean_reciprocal_rank({"a"}, ["a", "b", "c"]) == 1.0


def test_mrr_third_position():
    assert mean_reciprocal_rank({"c"}, ["a", "b", "c"]) == pytest.approx(1 / 3)


def test_mrr_no_relevant_found():
    assert mean_reciprocal_rank({"z"}, ["a", "b", "c"]) == 0.0


def test_ndcg_perfect_ranking_is_one():
    grades = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert ndcg_at_k(grades, ["a", "b", "c"], k=3) == 1.0


def test_ndcg_reversed_ranking_is_less_than_one():
    grades = {"a": 3.0, "b": 2.0, "c": 1.0}
    score = ndcg_at_k(grades, ["c", "b", "a"], k=3)
    assert score < 1.0


def test_ndcg_no_relevant_items_is_one_when_nothing_retrieved_matters():
    assert ndcg_at_k({}, ["a", "b"], k=2) == 1.0
