"""Prompt version `rerank:v1` (PRD §17).

Given one Requirement and a bounded list of candidate Evidence (already
retrieved by hybrid_search), judges whether any candidate directly, defensibly
supports the requirement — and if so, which one and how strongly.
"""

PROMPT_VERSION = "rerank:v1"

SYSTEM_PROMPT = """You are judging whether a candidate's actual technical evidence \
supports a specific job requirement. You are given the requirement and a short \
list of candidate evidence items (already retrieved as plausibly related).

Your job is to be skeptical, not generous:
- "strong" — the evidence directly and unambiguously demonstrates the \
requirement (e.g. requirement asks for "Kafka experience" and evidence shows \
Kafka producer/consumer code, not just a passing mention).
- "partial" — the evidence is related but doesn't fully establish the \
requirement (e.g. requirement asks for "production Kafka experience" but \
evidence only shows Kafka listed as a dependency with no usage code shown).
- "gap" — none of the candidates meaningfully support this requirement. Return \
best_evidence_index as null in this case.
- "unknown" — evidence might exist but the retrieved candidates don't give \
enough information to judge either way (distinct from "gap," which means the \
candidates actively don't support it).

Never say "strong" just because a candidate's retrieval score was high or a \
technology name matches — judge the actual substance of the evidence text \
against what the requirement specifically asks for. A vague or superficial \
match is "partial" at best, never "strong."

Score directness, depth, recency, and source_quality each from 0.0-1.0, and give \
a one-sentence reason for your label.
"""


def build_user_message(
    requirement_text: str, candidates: list[tuple[int, str, str, str]]
) -> str:
    """candidates: list of (index, title, normalized_claim, description)."""
    lines = "\n\n".join(
        f"[{i}] {title}\nClaim: {claim}\nDetail: {desc}"
        for i, title, claim, desc in candidates
    )
    return f"Requirement: {requirement_text}\n\nCandidate evidence:\n\n{lines}"
