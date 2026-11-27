"""Technology claims are grounded deterministically (claim_verify:v2).

Measured baseline (docs/product/metrics/verifier-eval-v1.json): a technology
appended to an otherwise true bullet ("..., deployed on Kubernetes") passed
the LLM verifier 20 times out of 20. With technologies as their own claims,
the guard checks each against the cited evidence text, which can't be talked
round.
"""

from proofhire_contracts import ClaimVerificationStatus

from proofhire_worker.intelligence.claim_finalizer import finalize_claim_status
from proofhire_worker.intelligence.fact_guard import FactCheckInput, FactGuardResult, check_fact

EVIDENCE = ["FastAPI service. Built an async API with Postgres and Redis caching."]


def check(value: str, evidence=EVIDENCE) -> FactGuardResult:
    return check_fact(FactCheckInput(claim_type="technology", asserted_value=value,
                                     evidence_texts=evidence))


def test_a_technology_named_in_the_cited_evidence_passes():
    assert check("FastAPI") == FactGuardResult.PASS
    assert check("redis") == FactGuardResult.PASS  # case-insensitive


def test_a_technology_absent_from_the_evidence_fails():
    assert check("Kubernetes") == FactGuardResult.FAIL_MISMATCH


def test_known_spellings_of_one_technology_match_both_ways():
    assert check("PostgreSQL") == FactGuardResult.PASS  # evidence says "Postgres"
    assert check("Postgres", ["Migrations on PostgreSQL 16."]) == FactGuardResult.PASS


def test_matching_respects_word_boundaries():
    assert check("Go", ["Deployed to Google Cloud."]) == FactGuardResult.FAIL_MISMATCH


def test_a_technology_claim_citing_no_evidence_fails_closed():
    assert check("FastAPI", evidence=None) == FactGuardResult.FAIL_NO_REFERENCE


def test_the_guard_overrides_a_verifier_talked_into_supported():
    status = finalize_claim_status(claim_type="technology", asserted_value="Kubernetes",
                                   llm_status="supported", profile_fact_value=None,
                                   evidence_texts=EVIDENCE)
    assert status == ClaimVerificationStatus.UNSUPPORTED


def test_employment_values_must_be_atomic():
    """Why v2 asks for one field per claim: a composite value matches no single
    profile-fact field, so v1's composites failed 19 of 20 true claims."""
    fact = {"employer": "Acme Analytics", "title": "Backend Engineer", "start_date": "2021"}

    def employment(value: str) -> FactGuardResult:
        return check_fact(FactCheckInput(claim_type="employment", asserted_value=value,
                                         profile_fact_value=fact))

    assert employment("Backend Engineer") == FactGuardResult.PASS
    assert employment("2021") == FactGuardResult.PASS
    assert employment("Principal Engineer") == FactGuardResult.FAIL_MISMATCH
    assert employment("Backend Engineer at Acme Analytics since 2021") == (
        FactGuardResult.FAIL_MISMATCH
    )
