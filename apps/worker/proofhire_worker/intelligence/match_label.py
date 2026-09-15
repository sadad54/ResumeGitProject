"""Match label resolution (PRD §17): "Never collapse Partial into Strong merely
to improve perceived fit."

This is deliberately a pure passthrough/validation function with no upgrade
path — there is no code here (or anywhere else in the coverage pipeline) that
takes a retrieval score, confidence, or any other signal and uses it to bump a
label upward. The LLM reranker's semantic judgment is the only source of the
label; this function's only job is to validate it against the enum and fall
back safely if the LLM returns something outside it.
"""

from proofhire_contracts import MatchLabel

_VALID = {m.value for m in MatchLabel}


def resolve_match_label(raw_label: str) -> MatchLabel:
    """Validates the LLM's raw label string against MatchLabel. An invalid/
    unrecognized value falls back to UNKNOWN (never to a more favorable label
    like STRONG) — an unparseable judgment is not evidence of a strong match."""
    normalized = raw_label.strip().lower()
    if normalized not in _VALID:
        return MatchLabel.UNKNOWN
    return MatchLabel(normalized)
