"""Best-effort server-side JD URL fetch (PRD §9.2, §40 "Login-walled job sites").

This is explicitly a fallback, not the primary frictionless path — many job
sites require JS rendering or a login wall that a plain HTTP GET can't get past.
The browser extension (Phase 8) capturing already-rendered, already-authenticated
page text is the PRD's stated primary route; this exists so pasting a URL still
works for the (large) share of postings that are plain server-rendered HTML.
"""

import re

import httpx

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")

MAX_CHARS = 20000


class JDFetchError(Exception):
    pass


def clean_html_to_text(html: str) -> str:
    html = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", html)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()[:MAX_CHARS]


async def fetch_and_extract_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 ProofHireBot/0.1"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JDFetchError(f"Could not fetch {url}: {exc}") from exc

    text = clean_html_to_text(response.text)

    if len(text) < 200:
        raise JDFetchError(
            "Fetched page had too little extractable text — likely JS-rendered or "
            "login-walled. Paste the job description text directly instead."
        )
    return text
