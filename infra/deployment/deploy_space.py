"""Deploy the single-container backend to a Hugging Face Docker Space, and
point the Vercel frontend at it.

One-time prerequisites (only you can do these):
    hf auth login        # a token with "write" scope
    vercel login         # only for --vercel

Then, from the repo root, in the Python environment the project is installed
in (the preflight imports the API's own config checks):
    python infra/deployment/deploy_space.py --space <hf-username>/proofhire [--vercel]

Nothing is uploaded until every preflight check passes:
1. The production environment is assembled: .env.production (generated,
   gitignored), provider keys and GitHub OAuth credentials from .env, and the
   URLs derived from the Space name.
2. The same validation the API and worker run at start
   (proofhire_api.config.deployment_config_errors) runs on exactly those
   values here first, so a bad value fails the deploy rather than the
   container.
3. check_models --probe runs against the configured provider with those
   keys and models: a retired model or a request the provider refuses (both
   seen on Groq) stops the deploy.
Then the Space is created or updated, secrets and variables are set, and
variables this script manages but no longer wants are deleted (the previous
version pinned LLM_MODEL_DEFAULT to a model Groq has since retired; a
leftover Space variable would keep overriding the fix). With --vercel,
NEXT_PUBLIC_API_BASE_URL is set for Production and the current production
deployment is rebuilt: the value is inlined at build time, so a rebuild is
required, and a redeploy uploads no local files. Secret values never reach
stdout; only names are printed.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in ("apps/api", "packages/contracts"):
    sys.path.insert(0, str(ROOT / path))

SECRETS = [
    "DATABASE_URL",
    "AUTH_SECRET_KEY",
    "TOKEN_ENCRYPTION_KEY",
    "GITHUB_OAUTH_CLIENT_ID",
    "GITHUB_OAUTH_CLIENT_SECRET",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "SENTRY_DSN",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
]
VARIABLES = [
    "ENVIRONMENT",
    "LLM_DEFAULT_PROVIDER",
    "WEB_BASE_URL",
    "API_BASE_URL",
    "GITHUB_OAUTH_REDIRECT_URI",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "STORAGE_BACKEND",
    "S3_ENDPOINT_URL",
    "S3_BUCKET_NAME",
    "S3_REGION",
    "DOWNLOAD_URL_TTL_SECONDS",
]
# Per-task model and reasoning overrides are passed through when set in
# .env.production, and removed from the Space when not.
MANAGED_PREFIXES = ("LLM_MODEL_", "LLM_REASONING_EFFORT_")

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
{web}. Source: https://github.com/sadad54/ResumeGitProject
"""

IGNORE = [
    "**/__pycache__/**",
    "**/*.pyc",
    "**/tests/**",
    "**/.pytest_cache/**",
    "**/node_modules/**",
    "**/.next/**",
    "**/*.md",
]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def assemble(env_path: Path, space: str, web: str, provider: str | None = None) -> dict[str, str]:
    env = load_env(env_path)
    if provider:
        env["LLM_DEFAULT_PROVIDER"] = provider
    # Values not in .env.production (GitHub OAuth app credentials, provider
    # keys) come from the dev .env so they needn't be copied by hand.
    dev = load_env(ROOT / ".env") if (ROOT / ".env").exists() else {}
    for k in SECRETS:
        env.setdefault(k, dev.get(k, ""))
    space_url = f"https://{space.replace('/', '-').lower()}.hf.space"
    env["WEB_BASE_URL"] = web
    env["API_BASE_URL"] = space_url
    env["GITHUB_OAUTH_REDIRECT_URI"] = f"{space_url}/api/v1/github/callback"
    env.setdefault("ENVIRONMENT", "production")
    # Groq: free tier, no card. Model defaults come from the code
    # (model_selection.PROVIDER_DEFAULTS) unless .env.production overrides.
    env.setdefault("LLM_DEFAULT_PROVIDER", "groq")
    env.setdefault("EMBEDDING_PROVIDER", "local")
    env.setdefault("STORAGE_BACKEND", "local")
    return env


def preflight(env: dict[str, str]) -> None:
    from proofhire_api.config import (
        Settings,
        deployment_config_errors,
        deployment_config_warnings,
    )

    # model_validate, not Settings(): the constructor would also read this
    # machine's environment and .env, and the check must see only these values.
    settings = Settings.model_validate(
        {name: env[name.upper()] for name in Settings.model_fields if env.get(name.upper())}
    )
    for warning in deployment_config_warnings(settings):
        print(f"warning: {warning}")
    errors = deployment_config_errors(settings)
    if errors:
        raise SystemExit("preflight failed, nothing uploaded:\n  - " + "\n  - ".join(errors))
    print("preflight: configuration ok")

    llm_env = {
        k: v
        for k, v in env.items()
        if k in {"LLM_DEFAULT_PROVIDER", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"}
        or k.startswith(MANAGED_PREFIXES)
    }
    child_env = {k: v for k, v in os.environ.items() if not k.startswith(MANAGED_PREFIXES)}
    result = subprocess.run(
        [sys.executable, "-m", "proofhire_worker.intelligence.check_models", "--probe"],
        env={**child_env, **llm_env},
        cwd=ROOT / "apps" / "worker",
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit("preflight failed (models, above), nothing uploaded")
    print("preflight: models ok")


def sync_variables(api, space: str, env: dict[str, str]) -> None:
    wanted = {k: env[k] for k in VARIABLES if env.get(k)}
    wanted.update({k: v for k, v in env.items() if k.startswith(MANAGED_PREFIXES) and v})
    for key, value in wanted.items():
        api.add_space_variable(space, key, value)
    for key in api.get_space_variables(space):
        managed = key in VARIABLES or key.startswith(MANAGED_PREFIXES)
        if managed and key not in wanted:
            api.delete_space_variable(space, key)
            print(f"variable {key}: removed (no longer configured)")
    print(f"variables set: {', '.join(sorted(wanted))}")


def point_vercel_at(api_url: str, web_url: str) -> None:
    """NEXT_PUBLIC_* values are inlined into the bundle at build time, so the
    live frontend keeps calling the old API (the audit found localhost:8000)
    until it is rebuilt with the new value."""
    subprocess.run(
        [
            "vercel",
            "env",
            "add",
            "NEXT_PUBLIC_API_BASE_URL",
            "production",
            "--value",
            api_url,
            "--force",
            "--no-sensitive",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["vercel", "redeploy", web_url, "--target", "production"], cwd=ROOT, check=True)
    print(f"vercel: NEXT_PUBLIC_API_BASE_URL={api_url}; production rebuilt")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--space", required=True, help="e.g. yourname/proofhire")
    ap.add_argument("--env", default=ROOT / ".env.production", type=Path)
    ap.add_argument("--web", default="https://proofhire-beta.vercel.app")
    ap.add_argument(
        "--vercel",
        action="store_true",
        help="also set NEXT_PUBLIC_API_BASE_URL on Vercel and rebuild production",
    )
    ap.add_argument(
        "--skip-preflight", action="store_true", help="upload without validating (not recommended)"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="assemble and preflight only; upload nothing"
    )
    ap.add_argument(
        "--provider",
        choices=["groq", "openai", "anthropic", "mock"],
        help="override LLM_DEFAULT_PROVIDER from the env file",
    )
    args = ap.parse_args()

    env = assemble(args.env, args.space, args.web, args.provider)
    if not args.skip_preflight:
        preflight(env)
    if args.dry_run:
        print("dry run: would set secrets", ", ".join(k for k in SECRETS if env.get(k)))
        print("dry run: would set variables", ", ".join(k for k in VARIABLES if env.get(k)))
        print(f"dry run: API would be {env['API_BASE_URL']}")
        return

    from huggingface_hub import HfApi

    api = HfApi()
    print(f"logged in to Hugging Face as {api.whoami()['name']}")
    api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)
    print(f"space: https://huggingface.co/spaces/{args.space}")

    api.upload_file(
        path_or_fileobj=io.BytesIO(README.format(web=args.web).encode()),
        path_in_repo="README.md",
        repo_id=args.space,
        repo_type="space",
    )
    api.upload_file(
        path_or_fileobj=ROOT / "infra/docker/Dockerfile.space",
        path_in_repo="Dockerfile",
        repo_id=args.space,
        repo_type="space",
    )
    api.upload_file(
        path_or_fileobj=ROOT / "infra/docker/space-entrypoint.sh",
        path_in_repo="infra/docker/space-entrypoint.sh",
        repo_id=args.space,
        repo_type="space",
    )
    for folder in (
        "apps/api",
        "apps/worker",
        "packages/contracts",
        "packages/prompts",
        "packages/evals",
    ):
        api.upload_folder(
            folder_path=ROOT / folder,
            path_in_repo=folder,
            repo_id=args.space,
            repo_type="space",
            ignore_patterns=IGNORE,
        )
        print(f"uploaded {folder}")

    for k in SECRETS:
        if env.get(k):
            api.add_space_secret(args.space, k, env[k])
            print(f"secret {k}: set")
        else:
            print(f"secret {k}: empty (skipped)")
    sync_variables(api, args.space, env)

    if args.vercel:
        point_vercel_at(env["API_BASE_URL"], args.web)

    api_url = env["API_BASE_URL"]
    print(
        f"\nAPI: {api_url} (the Space builds for a few minutes; check {api_url}/ready)"
        + (
            ""
            if args.vercel
            else f"\nFrontend: re-run with --vercel, or set NEXT_PUBLIC_API_BASE_URL={api_url} "
            "on Vercel and rebuild production"
        )
        + f"\nGitHub OAuth app: add {env['GITHUB_OAUTH_REDIRECT_URI']} as a callback URL"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # surface auth errors plainly
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
