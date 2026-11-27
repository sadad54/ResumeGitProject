"""Deploy the single-container backend to a VM you can SSH into (built for an
Oracle Cloud Always Free Ampere A1 instance), and point the Vercel frontend at it.

    python infra/deployment/deploy_vm.py --host <public-ip> --key <path-to-ssh-key> [--vercel]

The production environment and its preflight are the same as deploy_space.py
(configuration validation and a live model probe; nothing leaves this machine
until both pass). Then:
1. The environment is copied to /opt/proofhire/app.env on the VM (mode 600).
   Secret values never reach stdout.
2. infra/deployment/oracle/bootstrap.sh runs on the VM: installs Docker the
   first time, opens 80/443 in the VM's own firewall, builds
   infra/docker/Dockerfile.space from the git ref on GitHub, and runs it behind
   Caddy, which gets a Let's Encrypt certificate for <ip-with-dashes>.sslip.io.
3. With --vercel, NEXT_PUBLIC_API_BASE_URL is set and production rebuilt.

The VM builds from GitHub, so deploy a ref that has been pushed.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_space import ROOT, SECRETS, VARIABLES, assemble, point_vercel_at, preflight  # noqa: E402

BOOTSTRAP = ROOT / "infra/deployment/oracle/bootstrap.sh"


def default_hostname(ip: str) -> str:
    return f"{ip.replace('.', '-')}.sslip.io"


def ssh_base(args: argparse.Namespace) -> list[str]:
    opts = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30"]
    if args.key:
        opts += ["-i", str(args.key)]
    return opts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--host", required=True, help="the VM's public IPv4 address")
    ap.add_argument("--user", default="ubuntu")
    ap.add_argument("--key", type=Path, help="SSH private key for the VM")
    ap.add_argument("--hostname", help="public API hostname (default: <ip>.sslip.io)")
    ap.add_argument("--ref", default="master", help="git branch or tag to build on the VM")
    ap.add_argument("--env", default=ROOT / ".env.production", type=Path)
    ap.add_argument("--web", default="https://proofhire-beta.vercel.app")
    ap.add_argument("--provider", choices=["groq", "openai", "anthropic", "mock"])
    ap.add_argument("--vercel", action="store_true", help="also point the Vercel frontend here")
    ap.add_argument("--dry-run", action="store_true", help="assemble and preflight only")
    args = ap.parse_args()

    ipaddress.IPv4Address(args.host)  # fail early on a typo
    hostname = args.hostname or default_hostname(args.host)
    api_url = f"https://{hostname}"

    env = assemble(args.env, "unused/unused", args.web, args.provider)
    env["API_BASE_URL"] = api_url
    env["GITHUB_OAUTH_REDIRECT_URI"] = f"{api_url}/api/v1/github/callback"
    preflight(env)

    keep = [k for k in SECRETS + VARIABLES if env.get(k)]
    keep += [k for k in env if k.startswith(("LLM_MODEL_", "LLM_REASONING_EFFORT_")) and env[k]]
    if args.dry_run:
        print("dry run: would write", ", ".join(keep))
        print(f"dry run: API would be {api_url}")
        return

    target = f"{args.user}@{args.host}"
    opts = ssh_base(args)
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / "app.env"
        env_file.write_text("".join(f"{k}={env[k]}\n" for k in keep))
        subprocess.run(["ssh", *opts, target, "sudo mkdir -p /opt/proofhire && sudo chown $USER /opt/proofhire"], check=True)
        subprocess.run(["scp", *opts, str(env_file), f"{target}:/opt/proofhire/app.env"], check=True)
        subprocess.run(["scp", *opts, str(BOOTSTRAP), f"{target}:/opt/proofhire/bootstrap.sh"], check=True)
    print("environment copied:", ", ".join(keep))
    subprocess.run(
        ["ssh", *opts, target, f"chmod 600 /opt/proofhire/app.env && sh /opt/proofhire/bootstrap.sh {hostname} {args.ref}"],
        check=True,
    )

    if args.vercel:
        point_vercel_at(api_url, args.web)
    print(
        f"\nAPI: {api_url} (first HTTPS request may take a few seconds while Caddy gets the certificate)"
        f"\nVerify: python infra/docker/smoke_space.py --api {api_url}"
        f"\nGitHub OAuth app: add {env['GITHUB_OAUTH_REDIRECT_URI']} as a callback URL"
    )


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"error: remote step failed (exit {exc.returncode}); output above", file=sys.stderr)
        sys.exit(1)
