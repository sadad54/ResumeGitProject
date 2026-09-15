from proofhire_contracts import ClaimVerificationStatus

from proofhire_worker.intelligence.claim_finalizer import finalize_claim_status


def test_guarded_claim_with_correct_value_is_supported_even_if_llm_says_unsupported():
    """The guard is authoritative — an LLM being overly cautious about a
    correct, verbatim-matching employer claim must not block it."""
    status = finalize_claim_status(
        claim_type="employment",
        asserted_value="Google",
        llm_status="unsupported",
        profile_fact_value={"employer": "Google"},
        evidence_texts=None,
    )
    assert status == ClaimVerificationStatus.SUPPORTED


def test_guarded_claim_with_wrong_value_is_unsupported_even_if_llm_says_supported():
    """The critical direction: an LLM hallucinating confidence in a wrong
    employer must NOT be trusted over the deterministic check."""
    status = finalize_claim_status(
        claim_type="employment",
        asserted_value="Meta",
        llm_status="supported",
        profile_fact_value={"employer": "Google"},
        evidence_texts=None,
    )
    assert status == ClaimVerificationStatus.UNSUPPORTED


def test_guarded_metric_claim_ignores_llm_status_entirely():
    status = finalize_claim_status(
        claim_type="metric",
        asserted_value="47%",
        llm_status="supported",
        profile_fact_value=None,
        evidence_texts=["Improved throughput by 30%."],
    )
    assert status == ClaimVerificationStatus.UNSUPPORTED


def test_guarded_claim_never_resolves_to_partial_or_contradictory():
    """Exact-match validation has no concept of 'partially' matching an
    employer name — only SUPPORTED or UNSUPPORTED are reachable outcomes."""
    for llm_status in ["partially_supported", "contradictory", "supported", "unsupported"]:
        status = finalize_claim_status(
            claim_type="employment",
            asserted_value="Google",
            llm_status=llm_status,
            profile_fact_value={"employer": "Google"},
            evidence_texts=None,
        )
        assert status in (ClaimVerificationStatus.SUPPORTED, ClaimVerificationStatus.UNSUPPORTED)


def test_skill_claim_uses_llm_judgment_directly():
    status = finalize_claim_status(
        claim_type="skill",
        asserted_value="",
        llm_status="partially_supported",
        profile_fact_value=None,
        evidence_texts=None,
    )
    assert status == ClaimVerificationStatus.PARTIALLY_SUPPORTED


def test_skill_claim_with_garbage_llm_status_falls_back_to_unsupported():
    status = finalize_claim_status(
        claim_type="skill",
        asserted_value="",
        llm_status="totally sure!!",
        profile_fact_value=None,
        evidence_texts=None,
    )
    assert status == ClaimVerificationStatus.UNSUPPORTED
