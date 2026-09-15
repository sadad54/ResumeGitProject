"""Relevance-aware file selection (PRD §15 Stage 2).

Classifies each file in a repository tree into a priority bucket. P3 (and anything
matching an exclude pattern — vendor/generated/binary/secret-looking files) is
dropped before any content is fetched or sent to an LLM.
"""

import re
from pathlib import PurePosixPath

from proofhire_contracts import ArtifactPriority, SourceArtifactType

# Never fetch content for these — known secret/credential file patterns (PRD §27:
# "do not ingest .env, credentials, private keys or known secret file patterns").
SECRET_PATH_PATTERNS = [
    re.compile(r"(^|/)\.env(\..*)?$"),
    re.compile(r"(^|/)\.npmrc$"),
    re.compile(r"(^|/)id_rsa"),
    re.compile(r"\.pem$"),
    re.compile(r"\.pfx$"),
    re.compile(r"(^|/)credentials(\.json)?$"),
    re.compile(r"(^|/)secrets?\.(ya?ml|json)$"),
    re.compile(r"\.pgpass$"),
]

VENDOR_DIR_PATTERNS = [
    re.compile(r"(^|/)node_modules/"),
    re.compile(r"(^|/)\.venv/"),
    re.compile(r"(^|/)venv/"),
    re.compile(r"(^|/)vendor/"),
    re.compile(r"(^|/)dist/"),
    re.compile(r"(^|/)build/"),
    re.compile(r"(^|/)\.next/"),
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"(^|/)coverage/"),
    re.compile(r"(^|/)\.git/"),
]

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".tar",
    ".gz", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mov", ".exe", ".dll",
    ".so", ".dylib", ".class", ".jar", ".wasm", ".db", ".sqlite3",
}

README_PATTERN = re.compile(r"^readme(\.\w+)?$", re.IGNORECASE)
DEPENDENCY_MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "poetry.lock",
    "Pipfile", "go.mod", "Cargo.toml", "pom.xml", "build.gradle",
    "build.gradle.kts", "Gemfile", "composer.json",
}
DOCKER_FILENAMES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
K8S_HINT_DIRS = {"k8s", "kubernetes", "manifests", "helm"}
TERRAFORM_EXTENSIONS = {".tf", ".tfvars"}
NOTEBOOK_EXTENSIONS = {".ipynb"}
TEST_PATH_HINTS = ("test_", "_test.", "/tests/", "/test/", ".test.", ".spec.")


def is_excluded(path: str) -> bool:
    if any(p.search(path) for p in VENDOR_DIR_PATTERNS):
        return True
    if any(p.search(path) for p in SECRET_PATH_PATTERNS):
        return True
    ext = PurePosixPath(path).suffix.lower()
    return ext in BINARY_EXTENSIONS


def is_secret_like_path(path: str) -> bool:
    return any(p.search(path) for p in SECRET_PATH_PATTERNS)


def classify(path: str) -> tuple[SourceArtifactType, ArtifactPriority]:
    """Returns (artifact_type, priority) for a repository-relative file path.

    Priority classes per PRD §15:
    P0 — README, manifests, Dockerfiles, CI, K8s, Terraform, ML configs, benchmarks
    P1 — entry points, service boundaries, API defs, model/training/eval code, schemas
    P2 — representative implementation source files
    P3 — excluded before this function is even reached (see is_excluded)
    """
    name = PurePosixPath(path).name
    ext = PurePosixPath(path).suffix.lower()
    lower_path = path.lower()

    if README_PATTERN.match(name):
        return SourceArtifactType.README, ArtifactPriority.P0
    if name in DEPENDENCY_MANIFESTS:
        return SourceArtifactType.DEPENDENCY_MANIFEST, ArtifactPriority.P0
    if name in DOCKER_FILENAMES:
        return SourceArtifactType.DOCKER, ArtifactPriority.P0
    if ".github/workflows/" in path or name in {".gitlab-ci.yml", ".circleci/config.yml"}:
        return SourceArtifactType.CI_CONFIG, ArtifactPriority.P0
    if any(f"/{d}/" in f"/{lower_path}" for d in K8S_HINT_DIRS):
        return SourceArtifactType.KUBERNETES, ArtifactPriority.P0
    if ext in TERRAFORM_EXTENSIONS:
        return SourceArtifactType.TERRAFORM, ArtifactPriority.P0
    if "benchmark" in lower_path or "results" in lower_path and ext in {".md", ".json", ".csv"}:
        return SourceArtifactType.BENCHMARK, ArtifactPriority.P0

    if ext in NOTEBOOK_EXTENSIONS:
        return SourceArtifactType.NOTEBOOK, ArtifactPriority.P1
    if any(hint in lower_path for hint in TEST_PATH_HINTS):
        return SourceArtifactType.TEST, ArtifactPriority.P1
    if lower_path.endswith(".md") or "/docs/" in lower_path:
        return SourceArtifactType.DOCS, ArtifactPriority.P1
    if name in {"main.py", "app.py", "server.py", "index.ts", "index.js", "main.go"}:
        return SourceArtifactType.SOURCE_FILE, ArtifactPriority.P1

    return SourceArtifactType.SOURCE_FILE, ArtifactPriority.P2
