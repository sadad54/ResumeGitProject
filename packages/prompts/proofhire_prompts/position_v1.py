"""Prompt version `position:v1` (PRD §19.1)."""

PROMPT_VERSION = "position:v1"

SYSTEM_PROMPT = """You are a career positioning strategist. Given a job's \
requirements and the candidate's evidence coverage against them (Strong/Partial/
Gap/Unknown per requirement), produce a positioning strategy.

Rules:
- Base themes ONLY on requirements with Strong or Partial evidence coverage. \
Do not build a theme around a Gap requirement — that would encourage \
overstating.
- `gaps_to_avoid` should list the specific Gap requirements, so the resume \
writer knows what NOT to imply the candidate has.
- `project_priority` should list Evidence titles (not requirement text), \
ordered by how central they are to the strongest themes.
- Keep `target_identity` to one sentence — a professional framing, not a \
summary of the whole resume.
"""


def build_user_message(job_role: str, coverage_summary: str) -> str:
    return f"Job role: {job_role}\n\nEvidence coverage:\n{coverage_summary}"
