"""Prompt version `claim_verify:v2` (PRD §19.3).

v1 asked for exactly one judgment per bullet. Measured against planted
fabrications (apps/worker/scripts/eval_verifier.py, 20 documents), that let
through every invented technology appended to a true bullet (0/20 caught) and
all but one inflated-scope claim (1/20): judged as a whole, a mostly-true
bullet reads as supported. It also produced composite employment values
("Backend Engineer at Acme since 2021"), which the deterministic guard can't
match against any single profile-fact field, so it rejected 19 of 20 correct
employment claims.

v2 decomposes every bullet into atomic claims (one fact each, same
bullet_index), gives each hard fact a single-valued asserted_value the guard
can check verbatim, adds `technology` (guarded: must be named in the cited
evidence) and `scope` (leadership and ownership: unsupported unless the
evidence states it). A bullet fails if any one of its claims fails, which is
what the pipeline already does.
"""

PROMPT_VERSION = "claim_verify:v2"

SYSTEM_PROMPT = """You are a skeptical fact-checker reviewing generated resume \
content against the specific evidence and profile facts it must be grounded \
in. You are given a numbered list of bullets/lines.

Decompose every bullet into ATOMIC claims: one checkable fact per claim, each \
carrying the bullet's index. A single bullet usually yields several claims. \
Never judge a bullet as a whole: a bullet that is mostly true but adds one \
unsupported detail must produce a separate claim for that detail.

claim_type and asserted_value for each claim:
- employment / education / certification / award: one claim per field — the \
employer alone, the title alone, each date alone, the degree alone. \
asserted_value is that single value exactly as written (e.g. "Acme Analytics", \
"Backend Engineer", "2021"), never a combination. Set \
referenced_profile_fact_id to the matching profile fact, or null.
- metric: every number — percentages, counts, team sizes, durations, \
versions of scale ("6 engineers", "43%", "3x"). asserted_value is the number \
as written ("43%", "6"). Set referenced_evidence_id to the evidence that \
states it, or null.
- technology: every named technology, language, library, framework, tool, \
database, cloud service or platform (e.g. "Kubernetes", "FastAPI", "Redis"). \
One claim per technology; asserted_value is the name as written. Set \
referenced_evidence_id to an evidence item whose text names it, or null.
- scope: leadership, ownership, team or organisational claims ("led", \
"managed", "owned", "mentored", "team of"). Code evidence rarely establishes \
these: supported only if an evidence item explicitly states it.
- skill: a capability or practice that isn't a named technology.
- other: anything else factual.

status: supported / partially_supported / unsupported / contradictory, judged \
against the referenced source only. Be skeptical: a related technology or a \
similar project is not support. A claim with no plausible reference is \
"unsupported". Skip lines with no factual content at all.
"""


def build_user_message(
    indexed_bullets: list[tuple[int, str]], profile_facts_summary: str, evidence_summary: str
) -> str:
    bullets_text = "\n".join(f"[{i}] {text}" for i, text in indexed_bullets)
    return (
        f"Bullets to verify:\n{bullets_text}\n\n"
        f"Profile facts (id: value):\n{profile_facts_summary}\n\n"
        f"Evidence (id [repository]: title — claim — description):\n{evidence_summary}"
    )
