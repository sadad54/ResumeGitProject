"""Deploy the single-container backend to a Hugging Face Docker Space.

One-time prerequisites (only you can do these):
    pip install -U huggingface_hub        # if not already
    hf auth login                         # paste a token with "write" scope

Then, from the repo root:
    python infra/deployment/deploy_space.py --space <hf-username>/proofhire

It creates the Space if missing, uploads the backend source with
infra/docker/Dockerfile.space as the Space's Dockerfile, and pushes secrets
from .env.production (which is gitignored; see OPERATIONS.md for how the
values were generated). Re-run to redeploy. Nothing here is printed except
names — secret values never reach stdout.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]

SECRETS = [
    "DATABASE_URL", "AUTH_SECRET_KEY", "TOKEN_ENCRYPTION_KEY",
    "GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "SENTRY_DSN",
]
VARIABLES = ["ENVIRONMENT", "LLM_DEFAULT_PROVIDER", "WEB_BASE_URL", "API_BASE_URL",
             "GITHUB_OAUTH_REDIRECT_URI", "LLM_MODEL_DEFAULT"]

README = """---
title: ProofHire API
emoji: 🧾
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---
ProofHire backend (API + worker + Redis in one container). Frontend:
https://proofhire-beta.vercel.app. Source: https://github.com/sadad54/ResumeGitProject
"""

IGNORE = ["**/__pycache__/**", "**/*.pyc", "**/tests/**", "**/.pytest_cache/**",
          "**/node_modules/**", "**/.next/**", "**/*.md"]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True, help="e.g. yourname/proofhire")
    ap.add_argument("--env", default=ROOT / ".env.production", type=Path)
    ap.add_argument("--web", default="https://proofhire-beta.vercel.app")
    args = ap.parse_args()

    api = HfApi()
    user = api.whoami()["name"]
    print(f"logged in as {user}")

    env = load_env(args.env)
    # Fall back to the dev .env for values not in .env.production (GitHub OAuth
    # app credentials, provider keys) so they don't need copying by hand.
    dev = load_env(ROOT / ".env") if (ROOT / ".env").exists() else {}
    for k in SECRETS:
        env.setdefault(k, dev.get(k, ""))

    space_url = f"https://{args.space.replace('/', '-').lower()}.hf.space"
    env["WEB_BASE_URL"] = args.web
    env["API_BASE_URL"] = space_url
    env["GITHUB_OAUTH_REDIRECT_URI"] = f"{space_url}/api/v1/github/callback"
    env.setdefault("ENVIRONMENT", "production")
    # Groq by default: free tier, no card, and fast enough for a live demo.
    # Anthropic/OpenAI adapters stay in the codebase for later per-user BYOK;
    # override LLM_DEFAULT_PROVIDER in .env.production to use one of them here.
    env.setdefault("LLM_DEFAULT_PROVIDER", "groq")
    env.setdefault("LLM_MODEL_DEFAULT", "llama-3.3-70b-versatile")

    api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)
    print(f"space: https://huggingface.co/spaces/{args.space}")

    api.upload_file(path_or_fileobj=io.BytesIO(README.encode()), path_in_repo="README.md",
                    repo_id=args.space, repo_type="space")
    api.upload_file(path_or_fileobj=ROOT / "infra/docker/Dockerfile.space", path_in_repo="Dockerfile",
                    repo_id=args.space, repo_type="space")
    api.upload_file(path_or_fileobj=ROOT / "infra/docker/space-entrypoint.sh",
                    path_in_repo="infra/docker/space-entrypoint.sh", repo_id=args.space, repo_type="space")
    for folder in ("apps/api", "apps/worker", "packages/contracts", "packages/prompts", "packages/evals"):
        api.upload_folder(folder_path=ROOT / folder, path_in_repo=folder, repo_id=args.space,
                          repo_type="space", ignore_patterns=IGNORE)
        print(f"uploaded {folder}")

    for k in SECRETS:
        if env.get(k):
            api.add_space_secret(args.space, k, env[k])
            print(f"secret {k}: set")
        else:
            print(f"secret {k}: EMPTY (skipped)")
    for k in VARIABLES:
        if env.get(k):
            api.add_space_variable(args.space, k, env[k])
    print(f"\nAPI URL: {space_url}\nSet this as NEXT_PUBLIC_API_BASE_URL on Vercel and add\n"
          f"{env['GITHUB_OAUTH_REDIRECT_URI']} to the GitHub OAuth app's callback URLs.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # surface auth errors plainly
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
