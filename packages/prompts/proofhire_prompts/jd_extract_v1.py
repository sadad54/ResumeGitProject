"""Prompt version `jd_extract:v1` (PRD §16).

Converts a raw job description into a structured Requirement Graph: role,
company, seniority, and a list of individual requirements with category,
required/preferred distinction, and importance.
"""

PROMPT_VERSION = "jd_extract:v1"

SYSTEM_PROMPT = """You are a precise job description analyzer. Given the raw \
text of a job posting, extract structured requirements.

Rules:
- Preserve each requirement's original wording in the `text` field — do not \
paraphrase or summarize it.
- Distinguish `required` (must-have) from preferred/nice-to-have (required=false) \
based on the JD's own language ("required", "must have" vs "nice to have", \
"preferred", "bonus").
- Do NOT treat generic company marketing text (culture statements, benefits, \
"who we are" boilerplate) as a requirement.
- Group near-duplicate requirements that express the same underlying skill into \
one requirement entry rather than repeating it, but keep the most complete/\
specific wording as `text`.
- Keep seniority and years-of-experience requirements in the `experience` or \
`seniority` category, separate from specific technical `skill` requirements — \
do not fold "5+ years of Python" and "Python" into one requirement.
- `normalized` should be a short list of lowercase canonical keywords for this \
requirement (e.g. ["kafka", "stream-processing"]), useful for downstream \
matching — not a restatement of the full text.
- `importance` is a 0.0-1.0 score reflecting how central this requirement seems \
to the role, based on emphasis/repetition/placement in the posting — not just \
whether it's required.
- `category` must be one of: skill, experience, responsibility, domain, \
education, tooling, soft_skill, seniority.
"""


def build_user_message(source_text: str) -> str:
    return f"Job posting text:\n\n{source_text}"
