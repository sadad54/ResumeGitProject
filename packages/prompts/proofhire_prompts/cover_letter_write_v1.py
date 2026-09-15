"""Prompt version `cover_letter_write:v1` (PRD §19.2's "Resume Writer / Cover
Letter Writer" stage — same grounding discipline, a distinct prompt/schema
since the output shape and structure genuinely differ, not a mode of the
resume writer)."""

PROMPT_VERSION = "cover_letter_write:v1"

SYSTEM_PROMPT = """You are writing a cover letter for a specific job \
application. You may ONLY state facts drawn from the supplied Evidence and \
ProfileFacts below — never invent a skill, employer, date, or achievement \
that isn't in them, even if the job description asks for it.

Rules:
- Every factual claim (an employer, a project, an achievement) must be \
traceable to specific supplied Evidence or a ProfileFact.
- Preserve employer names and titles from ProfileFacts EXACTLY as given.
- Do not invent enthusiasm-driven specifics ("I've long admired your novel \
approach to X") unless that specific detail was supplied — generic enthusiasm \
framing that makes no unsupported factual claim is fine.
- 3-5 short paragraphs: an opening hook tied to the role, one or two body \
paragraphs grounded in specific supplied evidence, and a brief closing.
- Do not restate the entire resume — pick the 1-2 strongest, most relevant \
pieces of evidence per the positioning strategy.
"""


def build_user_message(positioning_summary: str, profile_facts_summary: str, evidence_summary: str) -> str:
    return (
        f"Positioning strategy:\n{positioning_summary}\n\n"
        f"Confirmed profile facts:\n{profile_facts_summary}\n\n"
        f"Available evidence (cite only these):\n{evidence_summary}"
    )


def build_repair_message(failed_paragraphs_summary: str) -> str:
    return (
        "The following paragraphs failed verification. Rewrite ONLY the "
        "affected paragraphs to either remove the unsupported claim or "
        "replace it with something the supplied Evidence/ProfileFacts "
        "actually support.\n\n"
        f"{failed_paragraphs_summary}"
    )
