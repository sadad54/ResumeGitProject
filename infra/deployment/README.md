# Deployment

## Topology (free tiers, $0/month)

| Piece | Where | URL / id |
|---|---|---|
| Frontend | Vercel (hobby) | https://proofhire-beta.vercel.app — project `proofhire`, root directory `apps/web` |
| Postgres + pgvector | Supabase (free) | project `proofhire` (`ltpuaecgvcxmepexwofb`, ap-southeast-1); app role `proofhire`, IPv4 session pooler |
| API + worker + Redis | Hugging Face Docker Space (free CPU) | one container from `infra/docker/Dockerfile.space`, deployed by `deploy_space.py` |
| LLM | Groq (free tier) | gpt-oss-120b / gpt-oss-20b; limits per model: 30 req/min, 1,000 req/day, 8K tokens/min, 200K tokens/day |
| Embeddings | inside the container | bge-small-en-v1.5 (ONNX, CPU), baked into the image — no key, no cost (ADR-0018) |

Deliberate differences from the separated layout in `OPERATIONS.md`:

- Redis runs inside the container and is ephemeral: rate-limit counters, the
  revoked-token denylist and queued jobs are lost when the Space restarts or
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

Everything else is scripted. Run the Python steps from the project's own
environment (the WSL venv used for development), because the deploy
preflight imports the API's configuration checks.

1. **Rotate the Groq key** (console.groq.com → API Keys): the current one has
   appeared in a chat transcript. Put the new one in `.env` as `GROQ_API_KEY`.
2. **Restore the Supabase project** if it's paused (dashboard → Restore). Free
   projects pause after 7 idle days; step 10 keeps it awake from then on.
3. **Fix `.env.production`**: line 8 still says `LLM_DEFAULT_PROVIDER=anthropic`
   and there is no Anthropic key, so the preflight refuses to deploy. Change it
   to `groq` (or pass `--provider groq` to the deploy script).
4. **Push the branch and open the PR.** CI's `space-image` job builds the exact
   image the Space will build, boots it against Postgres with production
   settings and smoke-tests it (`infra/docker/smoke_space.py`). Merge when green;
   Vercel deploys `master` automatically.
5. **Log in** to the two services the script talks to: `hf auth login` (a token
   with *write* scope) and `vercel login`.
6. **Dry run**, which assembles the production environment and runs every
   preflight check but uploads nothing:
   ```bash
   python infra/deployment/deploy_space.py --space <hf-username>/proofhire --dry-run
   ```
   It must print `preflight: configuration ok` and `preflight: models ok`.
7. **Deploy**, which also points the frontend at the Space and rebuilds it:
   ```bash
   python infra/deployment/deploy_space.py --space <hf-username>/proofhire --vercel
   ```
8. **GitHub OAuth app** (github.com → Settings → Developer settings → OAuth
   Apps → the ProofHire app): add the callback URL the script prints,
   `https://<hf-username>-proofhire.hf.space/api/v1/github/callback`.
9. **Verify** once the Space has built (a few minutes; watch its logs page):
   ```bash
   curl https://<hf-username>-proofhire.hf.space/ready
   python infra/docker/smoke_space.py --api https://<hf-username>-proofhire.hf.space
   ```
   Then sign up on the Vercel site, connect GitHub and sync a repository.
10. **Keep it awake** (optional): add a repository variable
    `PROOFHIRE_API_URL=https://<hf-username>-proofhire.hf.space` (Settings →
    Secrets and variables → Actions → Variables). `.github/workflows/keepalive.yml`
    then pings `/ready` daily, which wakes the Space and keeps Supabase active.
11. **Seed the demo account** (optional, recruiter-facing): see below.

## Redeploying

Re-run step 7. The preflight runs every time; the script also deletes Space
variables it manages but no longer sets (the previous version pinned
`LLM_MODEL_DEFAULT` to a model Groq has since retired). The container applies
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
