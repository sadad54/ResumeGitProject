"""Jake-inspired ATS Minimal template (PRD §21). Single-column, no images, no
tables. Technical Dense and Modern Editorial preserve the same single-column
content structure with different typography and spacing.

Not a reproduction of any specific third-party template's markup/CSS — an
original single-column layout inspired by common ATS-safe resume conventions
(PRD §21: "implement original template code... document attribution/license
where required" — no third-party code is used here, so no attribution is
owed).
"""

import html


def _esc(text: str) -> str:
    return html.escape(text or "")


_BASE_STYLE = """
body { font-family: Georgia, 'Times New Roman', serif; font-size: 10.5pt;
       color: #111; margin: 0; padding: 36px 48px; line-height: 1.4; }
h1 { font-size: 16pt; margin: 0 0 2px 0; font-weight: bold; }
.contact { font-size: 9.5pt; color: #333; margin-bottom: 10px; }
h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: 0.05em;
     border-bottom: 1px solid #333; margin: 14px 0 4px 0; padding-bottom: 2px; }
.entry-header { display: flex; justify-content: space-between; font-weight: bold; margin-top: 6px; }
.entry-dates { font-weight: normal; font-style: italic; }
ul { margin: 2px 0 6px 0; padding-left: 16px; }
li { margin-bottom: 2px; }
.skills { margin: 2px 0; }
p { margin: 6px 0; }
"""


TEMPLATE_STYLES = {
    "ats_minimal": "",
    "technical_dense": "body{font-family:Arial,sans-serif;font-size:10pt;line-height:1.3;padding:28px 40px} h2{margin-top:10px} li{margin-bottom:1px}",
    "modern_editorial": "body{font-family:Arial,sans-serif;line-height:1.5;padding:40px 48px} h2{color:#165b61;border-color:#165b61;letter-spacing:.08em} h1{font-family:Georgia,serif}",
}


def render_resume_html(content: dict, contact_email: str, template_id: str = "ats_minimal") -> str:
    if template_id not in TEMPLATE_STYLES:
        raise ValueError("Unknown resume template")
    summary = _esc(content.get("summary", ""))
    skills = ", ".join(_esc(s) for s in content.get("skills", []))

    experience_html = ""
    for entry in content.get("experience", []):
        bullets = "".join(f"<li>{_esc(b)}</li>" for b in entry.get("bullets", []))
        experience_html += f"""
        <div class="entry-header">
            <span>{_esc(entry.get('title', ''))} — {_esc(entry.get('employer', ''))}</span>
            <span class="entry-dates">{_esc(entry.get('start_date', ''))} – {_esc(entry.get('end_date', ''))}</span>
        </div>
        <ul>{bullets}</ul>
        """

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_STYLE}{TEMPLATE_STYLES[template_id]}</style></head>
<body>
<h1>Resume</h1>
<div class="contact">{_esc(contact_email)}</div>

<h2>Summary</h2>
<p>{summary}</p>

<h2>Skills</h2>
<p class="skills">{skills}</p>

<h2>Experience</h2>
{experience_html}
</body></html>"""


def render_cover_letter_html(content: dict, contact_email: str) -> str:
    paragraphs = "".join(f"<p>{_esc(p)}</p>" for p in content.get("body_paragraphs", []))
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_STYLE}</style></head>
<body>
<div class="contact">{_esc(contact_email)}</div>
{paragraphs}
</body></html>"""

