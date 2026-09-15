"""Secret scanner — runs on fetched file content BEFORE it is persisted or sent to
any LLM (PRD §27: "secret scanner before semantic extraction").

This is intentionally a fast, deterministic regex pass, not a full gitleaks-style
tool, for V1. A flagged file is excluded from ingestion entirely (not redacted and
kept) — safer default, and simpler than partial-redaction correctness.
"""

import re

_PATTERNS = [
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),  # Google API key
    re.compile(r"ghp_[0-9A-Za-z]{36}"),  # GitHub personal access token
    re.compile(r"github_pat_[0-9A-Za-z_]{22,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI-style secret key
    re.compile(r"sk-ant-[a-zA-Z0-9\-_]{20,}"),  # Anthropic-style secret key
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),  # Slack token
    re.compile(r"(?i)(api|secret|access)[_-]?key\s*[:=]\s*['\"][0-9A-Za-z\-_]{16,}['\"]"),
    re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
]


def contains_secret(content: str) -> bool:
    return any(pattern.search(content) for pattern in _PATTERNS)
