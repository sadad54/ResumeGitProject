# Deployment

## Live (free tiers)

| Piece | Where | URL / id |
|---|---|---|
| Frontend | Vercel (hobby, free) | https://proofhire-beta.vercel.app — project `proofhire`, root directory `apps/web` |
| Postgres + pgvector | Supabase (free) | project `proofhire` (`ltpuaecgvcxmepexwofb`, ap-southeast-1); app role `proofhire`, connection over the IPv4 session pooler; migrations 0001–0008 applied |
| API + worker + Redis | Hugging Face Docker Space (free) | one container from `infra/docker/Dockerfile.space`; deployed by `infra/deployment/deploy_space.py` |

This is the portfolio topology, chosen to cost $0/month. It differs from the
separated production layout in `OPERATIONS.md` in ways that are deliberate
and visible:

- Redis runs inside the API container and is ephemeral. Rate-limit counters,
  the revoked-token denylist and any queued jobs are lost when the Space
  restarts or sleeps (free Spaces sleep after 48 h idle; first request after
  that takes ~30–60 s). Postgres is external and durable.
- Rendered exports live on container disk and are regenerable from the
  database; they do not survive a restart.
- One replica, one worker process.

## Deploying the backend

Only the Hugging Face login is something the script cannot do for you.

```bash
pip install -U huggingface_hub
hf auth login                      # token with "write" scope from huggingface.co/settings/tokens
python infra/deployment/deploy_space.py --space <your-hf-username>/proofhire
```

The script creates the Space, uploads `apps/api`, `apps/worker`,
`packages/*` and the Dockerfile, and sets secrets from `.env.production`
(generated, gitignored) plus `GITHUB_OAUTH_*` and provider keys from `.env`.
Re-run it to redeploy. The container runs migrations on start.

Then:

1. **Vercel**: set `NEXT_PUBLIC_API_BASE_URL` to the Space URL the script
   prints and redeploy:
   `vercel env add NEXT_PUBLIC_API_BASE_URL production` then `vercel deploy --prod`.
2. **GitHub OAuth app**: add `<space-url>/api/v1/github/callback` to the
   app's authorization callback URLs, or the connect flow will fail.
3. **Provider keys**: `ANTHROPIC_API_KEY` (generation) and `OPENAI_API_KEY`
   (embeddings) must be set as Space secrets for real output. Without them
   the mock provider runs and generated documents are placeholders.
4. **Extension**: set `WEB_ORIGIN` in `apps/extension/config.js` and the
   `externally_connectable` match in `manifest.json` to the Vercel origin,
   then reload the unpacked extension.

## Seeding the live demo (recruiter-facing, no GitHub OAuth required)

A visitor can open a real, working account — real synced repo, real evidence
graph, real generated resume — without connecting their own GitHub, via a
seeded read-only guest account. `POST /api/v1/demo/session` mints a token for
it; `dependencies.get_current_user` blocks every mutating request from that
account regardless of route, so it's safe to expose publicly.

Populate it once (idempotent — re-run any time, e.g. after a schema change):

```bash
python apps/api/scripts/seed_demo.py --github-token <PAT with public_repo read> \
    --repo-owner sadad54 --repo-name ResumeGitProject
```

Needs the same `DATABASE_URL`/`GROQ_API_KEY` (or whichever provider
`LLM_DEFAULT_PROVIDER` selects) as the Space itself, so run it against the
Space's own environment (or export the same values locally) — it calls the
real pipeline (sync → evidence extraction → JD analysis → coverage →
generation) directly, not through Dramatiq, so it completes synchronously
with real errors instead of depending on a queue consumer.

## Verify

- `GET <space-url>/ready` → `{"status":"ready","postgres":"ok","redis":"ok"}`
- Sign up on the Vercel site, connect GitHub, sync a repository.
- `POST <space-url>/api/v1/demo/session` → 200 with a token; `GET /api/v1/auth/me`
  with it returns the seeded demo account.
