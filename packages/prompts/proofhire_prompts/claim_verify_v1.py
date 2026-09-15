"""Prompt version `claim_verify:v1` (PRD §19.3).

Judges each generated bullet/summary line (given as an indexed list — V1 runs
verification at bullet granularity, not further-decomposed sub-sentence
propositions, so a failure maps back to exactly one removable unit) against
the supplied Evidence/ProfileFacts, which are given WITH ids so the
deterministic fact guard can look up the exact reference afterward. This
prompt's own status/reason are advisory for guarded claim types — the guard's
exact-match check is authoritative for those.
"""

PROMPT_VERSION = "claim_verify:v1"

SYSTEM_PROMPT = """You are a skeptical fact-checker reviewing generated resume \
content against the specific evidence and profile facts it was supposed to be \
grounded in. You are given a numbered list of bullets/lines; produce exactly \
one claim judgment per bullet index (skip only lines with no factual content \
at all, e.g. a purely stylistic transition).

For each bullet:
1. Classify claim_type as one of: employment, education, certification, award, \
metric, skill, other.
2. For employment/education/certification/award claims, set asserted_value to \
the specific value being asserted (e.g. the employer name, or the date), and \
set referenced_profile_fact_id to the id of the ProfileFact it should match — \
null if you cannot identify one.
3. For metric claims, set asserted_value to the exact number/percentage \
asserted, and referenced_evidence_id to the id of the Evidence it should come \
from — null if you cannot identify one.
4. For skill/other claims, set referenced_evidence_id to the id of the \
Evidence that supports it, if any.
5. Judge status as supported/partially_supported/unsupported/contradictory \
based on whether the referenced source actually substantiates the claim as \
stated — be skeptical of vague or superficial matches, and never call \
something "supported" just because a related technology is mentioned \
somewhere. A claim with no plausible reference is "unsupported."
"""


def build_user_message(
    indexed_bullets: list[tuple[int, str]], profile_facts_summary: str, evidence_summary: str
) -> str:
    bullets_text = "\n".join(f"[{i}] {text}" for i, text in indexed_bullets)
    return (
        f"Bullets to verify:\n{bullets_text}\n\n"
        f"Profile facts (id: value):\n{profile_facts_summary}\n\n"
        f"Evidence (id: title — claim — description):\n{evidence_summary}"
    )
