"""Adversarial tests for the deterministic fact guard (PRD §19.4, §37 item 13).
Written and run before this guard is wired into the generation pipeline —
these are the cases a real writer LLM could plausibly produce, tested here
against pure Python logic with zero LLM involvement.
"""

from proofhire_worker.intelligence.fact_guard import (
    FactCheckInput,
    FactGuardResult,
    appears_verbatim,
    check_fact,
)

# --- appears_verbatim: the primitive everything else relies on ---


def test_exact_match_passes():
    assert appears_verbatim("Google", ["Worked at Google as an engineer."]) is True


def test_case_insensitive_match_passes():
    assert appears_verbatim("google", ["Worked at Google."]) is True


def test_missing_value_fails():
    assert appears_verbatim("Meta", ["Worked at Google."]) is False


def test_number_does_not_falsely_match_inside_larger_number():
    """The classic hallucination-adjacent bug: '20' must not match inside
    '2020' or '120' just because it's a substring."""
    assert appears_verbatim("20", ["Founded in 2020."]) is False
    assert appears_verbatim("20", ["Handled 120 requests per second."]) is False


def test_number_matches_at_word_boundary():
    assert appears_verbatim("20", ["Reduced latency by 20 percent."]) is True
    assert appears_verbatim("20%", ["Reduced latency by 20%."]) is True


def test_whitespace_normalization():
    assert appears_verbatim("30%", ["Improved   throughput  by\n30%   overall."]) is True


def test_empty_assertion_never_passes():
    assert appears_verbatim("", ["anything at all"]) is False


# --- check_fact: immutable ProfileFact-backed claims (employer, dates, degree) ---


def test_correct_employer_passes():
    result = check_fact(
        FactCheckInput(
            claim_type="employment",
            asserted_value="Google",
            profile_fact_value={"employer": "Google", "title": "SWE", "start_date": "2020", "end_date": "2022"},
        )
    )
    assert result == FactGuardResult.PASS


def test_invented_employer_fails():
    """A writer hallucinating a more impressive employer than what's on file."""
    result = check_fact(
        FactCheckInput(
            claim_type="employment",
            asserted_value="Meta",
            profile_fact_value={"employer": "Google", "title": "SWE", "start_date": "2020", "end_date": "2022"},
        )
    )
    assert result == FactGuardResult.FAIL_MISMATCH


def test_altered_date_fails():
    """A writer stretching employment dates to look more senior/continuous."""
    result = check_fact(
        FactCheckInput(
            claim_type="employment",
            asserted_value="2018",  # never worked there that early
            profile_fact_value={"employer": "Google", "title": "SWE", "start_date": "2020", "end_date": "2022"},
        )
    )
    assert result == FactGuardResult.FAIL_MISMATCH


def test_correct_date_passes():
    result = check_fact(
        FactCheckInput(
            claim_type="employment",
            asserted_value="2020",
            profile_fact_value={"employer": "Google", "title": "SWE", "start_date": "2020", "end_date": "2022"},
        )
    )
    assert result == FactGuardResult.PASS


def test_invented_degree_fails():
    result = check_fact(
        FactCheckInput(
            claim_type="education",
            asserted_value="PhD in Computer Science",
            profile_fact_value={"institution": "State University", "degree": "B.S. Computer Science"},
        )
    )
    assert result == FactGuardResult.FAIL_MISMATCH


def test_claim_with_no_profile_fact_reference_fails_closed():
    """No reference at all means we cannot verify — fail closed, never assume
    it's fine just because nothing contradicts it."""
    result = check_fact(FactCheckInput(claim_type="employment", asserted_value="Google", profile_fact_value=None))
    assert result == FactGuardResult.FAIL_NO_REFERENCE


def test_claim_with_empty_profile_fact_dict_fails_closed():
    result = check_fact(FactCheckInput(claim_type="employment", asserted_value="Google", profile_fact_value={}))
    assert result == FactGuardResult.FAIL_NO_REFERENCE


# --- check_fact: numeric metrics grounded in Evidence text ---


def test_verbatim_metric_from_evidence_passes():
    result = check_fact(
        FactCheckInput(
            claim_type="metric",
            asserted_value="30%",
            evidence_texts=["Improved API throughput by 30% after adding caching."],
        )
    )
    assert result == FactGuardResult.PASS


def test_invented_metric_not_in_evidence_fails():
    """The PRD §40 "Hallucinated metrics" risk, directly: a writer inventing a
    number that sounds plausible but was never in any source evidence."""
    result = check_fact(
        FactCheckInput(
            claim_type="metric",
            asserted_value="47%",
            evidence_texts=["Improved API throughput by 30% after adding caching."],
        )
    )
    assert result == FactGuardResult.FAIL_MISMATCH


def test_rounded_metric_fails_even_though_plausible():
    """Rounding 28.6% to 30% is still an invented number — the guard must not
    be lenient about 'close enough.'"""
    result = check_fact(
        FactCheckInput(
            claim_type="metric",
            asserted_value="30%",
            evidence_texts=["Improved throughput by 28.6% after adding caching."],
        )
    )
    assert result == FactGuardResult.FAIL_MISMATCH


def test_metric_with_no_evidence_reference_fails_closed():
    result = check_fact(FactCheckInput(claim_type="metric", asserted_value="30%", evidence_texts=None))
    assert result == FactGuardResult.FAIL_NO_REFERENCE


def test_metric_with_empty_evidence_list_fails_closed():
    result = check_fact(FactCheckInput(claim_type="metric", asserted_value="30%", evidence_texts=[]))
    assert result == FactGuardResult.FAIL_NO_REFERENCE


def test_metric_found_across_multiple_evidence_texts_passes():
    result = check_fact(
        FactCheckInput(
            claim_type="metric",
            asserted_value="99.9%",
            evidence_texts=["Unrelated evidence.", "Achieved 99.9% uptime over six months."],
        )
    )
    assert result == FactGuardResult.PASS


# --- check_fact: claim types outside the guard's scope ---


def test_generic_skill_claim_is_not_applicable():
    """Skill/feature claims aren't exact-match checkable — that's the semantic
    claim verifier's job (LLM-based), not this deterministic guard's."""
    result = check_fact(FactCheckInput(claim_type="skill", asserted_value="Python"))
    assert result == FactGuardResult.NOT_APPLICABLE


def test_unknown_claim_type_is_not_applicable():
    result = check_fact(FactCheckInput(claim_type="something_unrecognized", asserted_value="whatever"))
    assert result == FactGuardResult.NOT_APPLICABLE
