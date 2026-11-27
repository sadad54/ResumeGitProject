"""Deterministic fact guard (PRD §19.4, §37 item 13): the single most
safety-critical component in ProofHire. No LLM involved — every check here is
exact-match validation against already-confirmed ground truth (a ProfileFact's
stored value, or an Evidence item's actual text).

Design principle: the writer/claim-extractor must tag every "hard" claim
(employer, dates, degree, certification, numeric metric) with which specific
ProfileFact or Evidence it's citing, and the literal value being asserted. This
guard does NOT parse free-text prose to find entities — that would be fuzzy and
exactly the kind of thing that lets hallucinations slip through. It only checks
"does this asserted value appear verbatim in the thing it claims to come from."

A claim with no reference at all, or whose asserted value doesn't appear
verbatim in the reference, fails closed (FAIL) — there is no code path in this
module that can turn a failure into a pass by inference or fuzzy matching.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

# Claim types that must be grounded in an immutable ProfileFact record.
IMMUTABLE_CLAIM_TYPES = {"employment", "education", "certification", "award"}
METRIC_CLAIM_TYPE = "metric"
# A named technology must appear in the evidence the claim cites (claim_verify:v2).
# Planted fabrications like "..., deployed on Kubernetes" passed the LLM
# verifier 20 times out of 20 when judged as part of a mostly-true bullet
# (apps/worker/scripts/eval_verifier.py); an exact check can't be talked round.
TECHNOLOGY_CLAIM_TYPE = "technology"
EVIDENCE_GROUNDED_CLAIM_TYPES = {METRIC_CLAIM_TYPE, TECHNOLOGY_CLAIM_TYPE}

# Claim types this guard doesn't check at all (skill/scope/other claims are the
# claim *verifier's* job — an LLM judging semantic support against Evidence —
# not this guard's exact-match job).
GUARDED_CLAIM_TYPES = IMMUTABLE_CLAIM_TYPES | EVIDENCE_GROUNDED_CLAIM_TYPES

# The only non-verbatim matches this module allows: spellings of the same
# technology that evidence and writer commonly disagree on. Deliberately tiny
# and explicit; anything not listed must match as written.
TECHNOLOGY_ALIASES = {
    "postgres": "postgresql", "k8s": "kubernetes", "js": "javascript",
    "ts": "typescript", "nodejs": "node.js", "node": "node.js",
    "golang": "go", "gh actions": "github actions",
}


class FactGuardResult(StrEnum):
    PASS = "pass"
    FAIL_NO_REFERENCE = "fail_no_reference"
    FAIL_MISMATCH = "fail_mismatch"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class FactCheckInput:
    claim_type: str
    asserted_value: str
    profile_fact_value: dict | None = None
    evidence_texts: list[str] | None = None


def _normalize(text: str) -> str:
    return " ".join(str(text).strip().split())


def appears_verbatim(asserted_value: str, candidates: list[str]) -> bool:
    """True if asserted_value appears verbatim (case-insensitive, whitespace-
    normalized) in at least one candidate, with word-boundary checks so a
    number like "20" cannot falsely match inside "2020" or "120"."""
    normalized_assertion = _normalize(asserted_value)
    if not normalized_assertion:
        return False

    pattern = re.compile(re.escape(normalized_assertion), re.IGNORECASE)
    for candidate in candidates:
        normalized_candidate = _normalize(candidate)
        for match in pattern.finditer(normalized_candidate):
            start, end = match.span()
            before_ok = start == 0 or not normalized_candidate[start - 1].isalnum()
            after_ok = end == len(normalized_candidate) or not normalized_candidate[end].isalnum()
            if before_ok and after_ok:
                return True
    return False


def check_fact(input: FactCheckInput) -> FactGuardResult:
    if input.claim_type not in GUARDED_CLAIM_TYPES:
        return FactGuardResult.NOT_APPLICABLE

    if input.claim_type in IMMUTABLE_CLAIM_TYPES:
        if not input.profile_fact_value:
            return FactGuardResult.FAIL_NO_REFERENCE
        candidates = [str(v) for v in input.profile_fact_value.values() if v is not None]
        if appears_verbatim(input.asserted_value, candidates):
            return FactGuardResult.PASS
        return FactGuardResult.FAIL_MISMATCH

    if input.claim_type in EVIDENCE_GROUNDED_CLAIM_TYPES:
        if not input.evidence_texts:
            return FactGuardResult.FAIL_NO_REFERENCE
        values = [input.asserted_value]
        if input.claim_type == TECHNOLOGY_CLAIM_TYPE:
            canonical = TECHNOLOGY_ALIASES.get(_normalize(input.asserted_value).lower())
            values += [canonical] if canonical else []
            values += [a for a, c in TECHNOLOGY_ALIASES.items()
                       if c == _normalize(input.asserted_value).lower()]
        if any(appears_verbatim(v, input.evidence_texts) for v in values):
            return FactGuardResult.PASS
        return FactGuardResult.FAIL_MISMATCH

    return FactGuardResult.NOT_APPLICABLE  # unreachable given GUARDED_CLAIM_TYPES check above
