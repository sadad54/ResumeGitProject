"""Prompt version `resume_extract:v1` (PRD §13 ProfileFact, Phase 5).

Extracts structured, verbatim employment/education/certification/award facts
from an uploaded resume's raw text. These become ProfileFacts — the ground
truth the deterministic fact guard checks generated claims against — so
accuracy here matters more than completeness.
"""

from proofhire_prompts.untrusted import BOUNDARY_RULE, wrap_untrusted

PROMPT_VERSION = "resume_extract:v1"

SYSTEM_PROMPT = """You are extracting structured facts from a resume's raw \
text. Extract ONLY what is explicitly stated — never infer, estimate, or fill \
in a plausible-sounding value for something the resume doesn't state.

Rules:
- Copy employer names, job titles, institution names, degree names, and dates \
EXACTLY as written in the resume. Do not paraphrase, expand abbreviations, or \
correct formatting.
- If a date isn't stated (e.g. no end date because the job is current), use \
"Present" only if the resume itself says so ("Present", "Current", "-  Now"); \
otherwise leave it as an empty string rather than guessing.
- Do not invent employers, titles, or institutions that aren't in the text.
- List employment and education in the order they appear in the resume.
- """ + BOUNDARY_RULE + """
"""


def build_user_message(resume_text: str) -> str:
    return f"Resume text:\n\n{wrap_untrusted(resume_text)}"
