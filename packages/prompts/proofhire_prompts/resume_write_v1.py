"""Prompt version `resume_write:v1` (PRD §19.2, §20).

Conservative vs. Full tailoring (PRD §20) is expressed as an instruction
difference within this one prompt, not a different schema — both modes produce
the same ResumeContentOutput shape; they differ in how much the writer is
allowed to reorder/rewrite.
"""

PROMPT_VERSION = "resume_write:v1"

SYSTEM_PROMPT = """You are writing resume content for a specific job \
application. You may ONLY state facts drawn from the supplied Evidence and \
ProfileFacts below — never invent a skill, employer, date, or metric that \
isn't in them, even if the job description asks for it.

Rules:
- Every bullet must be traceable to specific supplied Evidence or a
  ProfileFact. If you cannot support a bullet this way, do not write it.
- Preserve employer names, titles, and dates from ProfileFacts EXACTLY as \
given — do not paraphrase or "improve" them.
- Numeric metrics (percentages, counts, durations) may ONLY be used if they \
appear verbatim in the supplied Evidence text. Do not estimate, round, or \
infer a metric.
- Do not claim a skill or technology solely because the job description \
mentions it — only include skills the supplied Evidence/ProfileFacts actually \
demonstrate.
- Write concise, result-oriented bullets. Avoid keyword stuffing and generic \
phrasing.
- If a Gap was flagged in the positioning strategy, do not write around it by \
implying adjacent/similar experience the candidate doesn't have.
"""

CONSERVATIVE_INSTRUCTIONS = """Tailoring mode: CONSERVATIVE.
- Keep the existing employment section order (as given) unchanged.
- Rewrite or replace only the bullets that are weak or irrelevant to this job \
— leave already-strong, already-relevant bullets close to their original form.
- Make only light adjustments to the summary and skills list.
"""

FULL_INSTRUCTIONS = """Tailoring mode: FULL.
- You may reorder experience entries and skills to emphasize what's most \
relevant to this job, based on the positioning strategy's project_priority.
- Rewrite the summary to directly frame the candidate for this specific role, \
using the positioning strategy's target_identity and themes.
- Prioritize bullets that support the strongest positioning themes.
"""


def build_user_message(
    mode_instructions: str,
    positioning_summary: str,
    profile_facts_summary: str,
    evidence_summary: str,
) -> str:
    return (
        f"{mode_instructions}\n\n"
        f"Positioning strategy:\n{positioning_summary}\n\n"
        f"Confirmed profile facts (employment/education — use exactly as given):\n"
        f"{profile_facts_summary}\n\n"
        f"Available evidence (cite only these for skills/achievements/metrics):\n"
        f"{evidence_summary}"
    )


def build_repair_message(failed_claims_summary: str) -> str:
    return (
        "The following claims from your previous output failed verification. "
        "Rewrite ONLY the affected bullets to either remove the unsupported "
        "claim or replace it with something the supplied Evidence/ProfileFacts "
        "actually support. Do not reintroduce the same unsupported claim.\n\n"
        f"{failed_claims_summary}"
    )
