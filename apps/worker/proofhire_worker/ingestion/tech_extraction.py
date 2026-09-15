"""Deterministic technology extraction (PRD §15 Stage 3) — runs BEFORE any LLM call,
on P0 artifacts (manifests, CI configs, Dockerfiles). Cheap, exact-match signal that
also feeds Evidence confidence scoring in Phase 2 (deterministic + semantic fusion).
"""

import json
import re

_FRAMEWORK_HINTS: dict[str, list[str]] = {
    "fastapi": ["python"],
    "django": ["python"],
    "flask": ["python"],
    "next": ["typescript", "javascript"],
    "react": ["typescript", "javascript"],
    "express": ["typescript", "javascript"],
    "dramatiq": ["python"],
    "celery": ["python"],
    "sqlalchemy": ["python"],
    "pytorch": ["python"],
    "torch": ["python"],
    "tensorflow": ["python"],
    "scikit-learn": ["python"],
    "pandas": ["python"],
}


def extract_from_package_json(content: str) -> dict:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return {}
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return {
        "language": "javascript/typescript",
        "dependencies": sorted(deps.keys()),
        "frameworks": sorted(name for name in _FRAMEWORK_HINTS if name in deps),
    }


def extract_from_pyproject_toml(content: str) -> dict:
    # Lightweight regex extraction rather than a full TOML parse, to avoid adding a
    # tomllib version dependency edge case; good enough for dependency name signal.
    deps = re.findall(r'^\s*"?([a-zA-Z0-9_\-]+)(?:\[[^\]]*\])?\s*[><=~^]', content, re.MULTILINE)
    return {
        "language": "python",
        "dependencies": sorted(set(deps)),
        "frameworks": sorted(name for name in _FRAMEWORK_HINTS if name in {d.lower() for d in deps}),
    }


def extract_from_requirements_txt(content: str) -> dict:
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[><=~\[;]", line, maxsplit=1)[0].strip()
        if name:
            deps.append(name.lower())
    return {
        "language": "python",
        "dependencies": sorted(set(deps)),
        "frameworks": sorted(name for name in _FRAMEWORK_HINTS if name in deps),
    }


def extract_from_dockerfile(content: str) -> dict:
    base_images = re.findall(r"^FROM\s+(\S+)", content, re.MULTILINE | re.IGNORECASE)
    return {"container": True, "base_images": base_images}


def extract_from_ci_config(path: str, content: str) -> dict:
    if ".github/workflows/" in path:
        provider = "github_actions"
    elif ".gitlab-ci" in path:
        provider = "gitlab_ci"
    elif "circleci" in path:
        provider = "circleci"
    else:
        provider = "unknown"
    return {"ci_provider": provider}


def extract(path: str, content: str) -> dict:
    """Dispatches to the right deterministic extractor based on filename."""
    name = path.rsplit("/", 1)[-1]
    if name == "package.json":
        return extract_from_package_json(content)
    if name == "pyproject.toml":
        return extract_from_pyproject_toml(content)
    if name == "requirements.txt":
        return extract_from_requirements_txt(content)
    if name in {"Dockerfile"} or name.startswith("Dockerfile."):
        return extract_from_dockerfile(content)
    if ".github/workflows/" in path or name in {".gitlab-ci.yml"}:
        return extract_from_ci_config(path, content)
    return {}
