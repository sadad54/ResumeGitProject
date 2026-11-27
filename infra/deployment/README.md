# Deployment

## Topology (free tiers, $0/month)

| Piece | Where | URL / id |
|---|---|---|
| Frontend | Vercel (hobby) | https://proofhire-beta.vercel.app — project `proofhire`, root directory `apps/web` |
| Postgres + pgvector | Supabase (free) | project `proofhire` (`ltpuaecgvcxmepexwofb`, ap-southeast-1); app role `proofhire`, IPv4 session pooler |
| API + worker + Redis | Oracle Cloud Always Free VM (Ampere A1, arm64) | one container from `infra/docker/Dockerfile.space` behind Caddy (Let's Encrypt on `<ip>.sslip.io`), deployed by `deploy_vm.py` |
| LLM | Groq (free tier) | gpt-oss-120b / gpt-oss-20b; limits per model: 30 req/min, 1,000 req/day, 8K tokens/min, 200K tokens/day |
| Embeddings | inside the container | bge-small-en-v1.5 (ONNX, CPU), baked into the image — no key, no cost (ADR-0018) |

Deliberate differences from the separated layout in `OPERATIONS.md`:

- Redis runs inside the container and is ephemeral: rate-limit counters, the
  revoked-token denylist and queued jobs are lost when the container restarts or
  sleeps. Postgres is external and durable.
- Rendered PDFs live on container disk unless `STORAGE_BACKEND=s3` (any
  S3-compatible store; see `.env.example`). A vanished export answers 410 and
  the UI offers to export again.
- One replica, one worker process (two threads).
- Free-tier throughput, measured (`docs/product/metrics/e2e-live.json`): three
  small repositories took 10 extraction calls (~37K tokens on gpt-oss-20b); a
  job analysis plus a verified resume took ~12 calls (~16K tokens). At 200K
  tokens/day per model that is roughly five such accounts' first syncs a day
  before gpt-oss-20b's quota runs out; the container's `check_models --probe`
  and the retry policy fail fast when a daily quota is spent.

## Going live: the steps only you can do, in order

Hugging Face stopped hosting Docker Spaces on the free CPU tier (the deploy
got `402 Payment Required` on 2026-11-28), so the backend runs on an Oracle
Cloud Always Free VM instead. `deploy_space.py` is kept for anyone with a PRO
account; `deploy_vm.py` reuses its environment assembly and preflight.

1. **Oracle account** at cloud.oracle.com (Always Free). It asks for a card to
   verify identity; Always Free resources are not charged. Pick a home region
   close to Supabase (ap-southeast-1 → Singapore); it can't be changed later.
2. **Create the VM**: Compute → Instances → Create. Image *Canonical Ubuntu
   24.04*, shape *VM.Standard.A1.Flex* with 2 OCPU / 12 GB (inside the free
   4 / 24; a smaller shape also helps with "out of host capacity" errors —
   retry later or pick another availability domain if you hit one). Keep
   "assign a public IPv4 address" on and **download the generated private
   key** (e.g. to `C:\Users\<you>\.ssh\proofhire-oracle.key`).
3. **Open ports 80 and 443**: the instance's subnet → Security List → Add
   Ingress Rules: source `0.0.0.0/0`, TCP, destination ports `80,443`.
   (The bootstrap script opens them in the VM's own firewall too.)
4. **Merge the PR** once CI is green, so `master` has what the VM builds.
5. **Dry run** (repo root, in the project's Python 3.13 venv):
   ```bash
   python infra/deployment/deploy_vm.py --host <public-ip> --dry-run
   ```
6. **Deploy**, which also points the frontend at the VM and rebuilds it:
   ```bash
   python infra/deployment/deploy_vm.py --host <public-ip> --key <path-to-key> --vercel
   ```
   The first run installs Docker and builds the image on the VM (~10 minutes
   on 2 OCPU); later runs rebuild only changed layers.
7. **GitHub OAuth app**: add the callback URL the script prints,
   `https://<ip-with-dashes>.sslip.io/api/v1/github/callback`.
8. **Verify**:
   ```bash
   curl https://<ip-with-dashes>.sslip.io/ready
   python infra/docker/smoke_space.py --api https://<ip-with-dashes>.sslip.io
   ```
9. **Keep Supabase awake** (optional): repository variable
   `PROOFHIRE_API_URL=https://<ip-with-dashes>.sslip.io`; the keep-alive
   workflow pings `/ready` daily so the free database never idles into a pause.
10. **Seed the demo account** (optional, recruiter-facing): see below.

Oracle may reclaim Always Free instances that sit idle for 7 days (very low
CPU, network and memory use). The daily keep-alive keeps this one active in
practice; if the VM is ever reclaimed, steps 2, 3 and 6 rebuild it.

## Redeploying

Re-run step 6 (add `--ref <branch>` to deploy something other than `master`).
The preflight runs every time, and the VM's environment file is rewritten
from scratch, so a variable removed from `.env.production` is gone on the
next deploy. The data volume and the TLS certificate survive. The container applies
migrations, probes the configured models and re-embeds any evidence embedded
by a different model on start.

## Seeding the live demo

`POST /api/v1/demo/session` signs a visitor into a read-only guest account;
`dependencies.get_current_user` blocks every write from it. Populate it by
running the real pipeline once against the production database:

```bash
export DATABASE_URL=<production DATABASE_URL> GROQ_API_KEY=<key> LLM_DEFAULT_PROVIDER=groq
python apps/api/scripts/seed_demo.py --github-token <fine-grained PAT: public repositories, read-only> \
    --repo-owner sadad54 --repo-name ResumeGitProject
```

It stores that token (encrypted) on the demo account so the sync can read the
repository, so use a token that can read public repositories and nothing
else. ResumeGitProject is about 21 extraction calls (~100K tokens, half of
gpt-oss-20b's daily quota): seed on a day with quota to spare.

## Verify

- `GET <space-url>/ready` → `{"status":"ready","postgres":"ok","redis":"ok"}`
- `python infra/docker/smoke_space.py --api <space-url>` → all checks pass
- `POST <space-url>/api/v1/demo/session` → 200 with a token, once seeded
