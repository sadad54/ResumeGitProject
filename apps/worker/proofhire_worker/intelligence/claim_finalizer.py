"""Combines the deterministic fact guard with the LLM claim verifier's semantic
judgment into one final ClaimVerificationStatus per claim (PRD §19.3-§19.4).

For guarded claim types (employment/education/certification/award/metric), the
fact guard is authoritative — the LLM's own status/reason for those types is
advisory only and never overrides a guard failure into a pass. For all other
types, the LLM's semantic judgment is what we have, validated against the enum.
"""

from proofhire_contracts import ClaimVerificationStatus

from proofhire_worker.intelligence.fact_guard import (
    GUARDED_CLAIM_TYPES,
    FactCheckInput,
    FactGuardResult,
    check_fact,
)

_VALID_STATUSES = {s.value for s in ClaimVerificationStatus}


def _resolve_llm_status(raw_status: str) -> ClaimVerificationStatus:
    normalized = raw_status.strip().lower()
    if normalized not in _VALID_STATUSES:
        return ClaimVerificationStatus.UNSUPPORTED  # unparseable judgment is not evidence of support
    return ClaimVerificationStatus(normalized)


def finalize_claim_status(
    *,
    claim_type: str,
    asserted_value: str,
    llm_status: str,
    profile_fact_value: dict | None,
    evidence_texts: list[str] | None,
) -> ClaimVerificationStatus:
    if claim_type in GUARDED_CLAIM_TYPES:
        guard_result = check_fact(
            FactCheckInput(
                claim_type=claim_type,
                asserted_value=asserted_value,
                profile_fact_value=profile_fact_value,
                evidence_texts=evidence_texts,
            )
        )
        # The guard is authoritative for guarded types — it can only produce
        # SUPPORTED or UNSUPPORTED, never PARTIALLY_SUPPORTED or CONTRADICTORY,
        # since exact-match validation has no concept of "partially" matching
        # an employer name or a percentage.
        return (
            ClaimVerificationStatus.SUPPORTED
            if guard_result == FactGuardResult.PASS
            else ClaimVerificationStatus.UNSUPPORTED
        )

    return _resolve_llm_status(llm_status)
