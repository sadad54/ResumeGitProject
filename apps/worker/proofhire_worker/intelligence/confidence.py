"""Confidence scoring (PRD §15 Stage 6): combines deterministic signals, source
count, and semantic extraction confidence. Contradiction checks are deferred —
they require cross-referencing against already-persisted evidence semantically,
which is a reasonable Phase 4+ enhancement rather than a Phase 2 blocker, since
retrieval/matching infrastructure to do that well doesn't exist yet.

Kept as a pure function so it's independently testable without a DB or LLM call.
"""

# Small, capped boosts rather than large multipliers — a corroborating
# deterministic signal or extra source should nudge confidence, not dominate the
# LLM's own semantic assessment of how directly the text supports the claim.
DETERMINISTIC_MATCH_BOOST = 0.05
MAX_DETERMINISTIC_BOOST = 0.15
EXTRA_SOURCE_BOOST = 0.03
MAX_SOURCE_BOOST = 0.09


def combine_confidence(
    semantic_confidence: float,
    source_count: int,
    skill_names: list[str],
    deterministic_tech: set[str],
) -> float:
    matches = sum(1 for skill in skill_names if skill.strip().lower() in deterministic_tech)
    deterministic_boost = min(matches * DETERMINISTIC_MATCH_BOOST, MAX_DETERMINISTIC_BOOST)

    extra_sources = max(0, source_count - 1)
    source_boost = min(extra_sources * EXTRA_SOURCE_BOOST, MAX_SOURCE_BOOST)

    return min(1.0, semantic_confidence + deterministic_boost + source_boost)
