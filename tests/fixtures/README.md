# Fixtures

## Fixture repository

ProofHire uses **this repository itself** (`sadad54/ResumeGitProject` on GitHub) as
its Phase 1+ fixture repo for GitHub ingestion and evidence extraction — no local
clone needed under `repos/`. Once Phase 1's GitHub OAuth + sync is built, connect
this same account/repo and it becomes the first thing evidence gets extracted from
(README, `pyproject.toml`/`package.json` manifests, `.github/workflows/ci.yml`,
`infra/docker/docker-compose.yml`, source code).

`repos/` is kept for any *additional* external fixture repos added later (e.g. to
diversify the eval benchmark in Phase 9) and is gitignored except for `.gitkeep`.

## Fixture job descriptions

- `jobs/fixture_jd_1.txt` — mid-level backend/full-stack SWE posting, used from
  Phase 3 onward to validate JD requirement extraction, coverage matching, and
  generation end-to-end.
- AI/ML-flavored and frontend-flavored JDs are added by Phase 3-4, ahead of the
  Phase 9 100+ JD benchmark (see `packages/evals`).
