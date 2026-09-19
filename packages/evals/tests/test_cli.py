import pytest
from proofhire_evals.cli import measured_budget, score


def fixtures():
    gold = [
        {
            "id": "fixture",
            "family": "backend",
            "requirements": ["rest"],
            "evidence_matches": {"rest": {"api": 2}},
            "review": {"status": "synthetic_smoke"},
        }
    ]
    runs = [
        {
            "id": "fixture",
            "requirements": ["rest"],
            "ranked_evidence": {"rest": ["api"]},
            "claims": 1,
            "unsupported_claims": 0,
            "immutable_facts": 1,
            "preserved_facts": 1,
            "parse_back_attempts": 1,
            "parse_back_successes": 1,
            "secret_leaks": 0,
            "input_tokens": 20,
            "output_tokens": 10,
            "cost_usd": 0.01,
            "latency_ms": 100,
        }
    ]
    return gold, runs


def test_smoke_does_not_claim_release_readiness():
    gold, runs = fixtures()
    assert score(gold, runs)["passed"]
    assert not score(gold, runs, release=True)["passed"]


def test_missing_metrics_fail_closed():
    gold, runs = fixtures()
    del runs[0]["unsupported_claims"]
    assert not score(gold, runs)["passed"]


def test_no_subset_cherry_picking():
    gold, runs = fixtures()
    runs[0]["id"] = "different"
    with pytest.raises(ValueError):
        score(gold, runs)


def test_no_duplicate_rank_inflation():
    gold, runs = fixtures()
    runs[0]["ranked_evidence"]["rest"] = ["api", "api"]
    with pytest.raises(ValueError):
        score(gold, runs)


@pytest.mark.parametrize("cost", [0, -1, float("nan")])
def test_budget_requires_real_measurements(cost):
    with pytest.raises(ValueError):
        measured_budget([{"provider": "openai", "cost_usd": cost}], 100)


def test_measured_budget_for_both_providers():
    result = measured_budget(
        [
            {"provider": "openai", "cost_usd": 0.03},
            {"provider": "anthropic", "cost_usd": 0.04},
        ],
        100,
    )
    assert result["proposed_cap_usd"] == 8.75
