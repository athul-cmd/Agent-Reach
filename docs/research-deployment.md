# Research Studio Deployment

This is the canonical deployment guide for the free-first hosted architecture.

The default production model is:

1. `nodepad-main/` on Vercel
2. Supabase for Auth, Postgres, and Storage
3. Upstash QStash calling the internal scheduler route every 5 minutes
4. GitHub Actions running Python jobs by `job_run_id`

`Railway` is optional and paid. It is not part of the default operating model.

## 1. Apply the database SQL

Apply both SQL files to the same Supabase project:

```text
agent_reach/research/sql/postgres_schema.sql
nodepad-main/supabase/research_studio.sql
```

The first file creates the research tables, leasing fields, and `claim_due_job_runs` function.

The second file creates the app-side encrypted settings tables and RLS policies used by the Next.js app.

## 2. Configure Vercel

Deploy `nodepad-main/` to Vercel.

Set these environment variables in the Vercel project:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<supabase-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<supabase-service-role-key>
AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY=<supabase-service-role-key>

RESEARCH_SETTINGS_ENCRYPTION_KEY=<32-byte-random-secret>

AGENT_REACH_RESEARCH_DB_BACKEND=supabase
AGENT_REACH_RESEARCH_DB_DSN=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
AGENT_REACH_RESEARCH_BLOB_BACKEND=supabase
AGENT_REACH_RESEARCH_BLOB_BUCKET=research-artifacts
AGENT_REACH_RESEARCH_BLOB_PREFIX=agent-reach/research
AGENT_REACH_RESEARCH_SUPABASE_URL=https://<project-ref>.supabase.co

GITHUB_ACTIONS_DISPATCH_TOKEN=<github-token-with-actions-write>
GITHUB_ACTIONS_REPO_OWNER=<github-owner>
GITHUB_ACTIONS_REPO_NAME=<repo-name>
GITHUB_ACTIONS_WORKFLOW_FILE=research-job-runner.yml
GITHUB_ACTIONS_WORKFLOW_REF=main

QSTASH_CURRENT_SIGNING_KEY=<upstash-current-signing-key>
QSTASH_NEXT_SIGNING_KEY=<upstash-next-signing-key>
```

Notes:

1. `RESEARCH_API_BASE_URL` is optional and fallback-only. Do not use it as the normal dashboard path.
2. `RESEARCH_API_ACCESS_TOKEN` is only needed if you still run the legacy Python HTTP API for operator-only fallback routes.
3. `SUPABASE_SERVICE_ROLE_KEY` and `AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY` can hold the same value.

## 3. Configure GitHub Actions

The repo already includes:

1. `.github/workflows/research-job-runner.yml`
2. `.github/workflows/research-scheduler-fallback.yml`

Set these repository secrets in GitHub:

```bash
AGENT_REACH_RESEARCH_DB_BACKEND
AGENT_REACH_RESEARCH_DB_DSN
AGENT_REACH_RESEARCH_BLOB_BACKEND
AGENT_REACH_RESEARCH_BLOB_BUCKET
AGENT_REACH_RESEARCH_BLOB_PREFIX
AGENT_REACH_RESEARCH_SUPABASE_URL
AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY
RESEARCH_SETTINGS_ENCRYPTION_KEY
OPENAI_API_KEY
```

If you want the runner to rely only on encrypted settings saved through the app, `OPENAI_API_KEY` can stay unset. Keep it only as an operator fallback.

The Vercel-side `GITHUB_ACTIONS_DISPATCH_TOKEN` must be a GitHub token that can dispatch workflows on this repo.

## 4. Configure QStash

Create a QStash schedule that sends `POST` requests every 5 minutes to:

```text
https://<your-vercel-domain>/api/internal/scheduler
```

The internal route verifies the `Upstash-Signature` header using:

```bash
QSTASH_CURRENT_SIGNING_KEY
QSTASH_NEXT_SIGNING_KEY
```

Recommended schedule:

1. cadence: every 5 minutes
2. method: `POST`
3. body: empty JSON object `{}` or no body
4. retries: leave enabled

The scheduler route claims due jobs in Supabase and dispatches `research-job-runner.yml` once per claimed job.

## 5. First-run sequence

After deployment:

1. sign in to `/research/login`
2. open `/research/settings`
3. save the OpenAI key in the settings UI
4. create the research profile
5. add writing samples or import LinkedIn posts
6. open the dashboard and run system verification
7. trigger one manual run from the dashboard

Expected result:

1. the manual run inserts pending jobs
2. the app dispatches GitHub Actions immediately
3. the runner executes `agent-reach research run job --job-run-id <id>`
4. the dashboard starts showing source items, clusters, ideas, and job history

## 6. Failure behavior

The intended failure path is explicit:

1. if GitHub dispatch env is incomplete, manual runs fail with a clear operator error
2. if the scheduler route cannot dispatch a claimed job, the lease is released and the job is re-scheduled
3. if a Python job fails, the job run stays recorded with `failed` status and an error summary

## 7. Verification commands

Useful checks:

```bash
cd nodepad-main
npm run typecheck
npm run test

cd ..
python3 -m pytest tests/test_research_store.py tests/test_research_cli.py
```

For Python runtime verification on a configured machine:

```bash
agent-reach research verify storage
agent-reach research verify sources
agent-reach research run dispatch --execute
```

## 8. Local fallback

If you need a local or operator-only fallback:

1. run the Next.js app locally
2. run Python commands directly from the repo root
3. optionally run the legacy Python API behind `RESEARCH_API_BASE_URL`

That is not the primary production path. The normal path is direct app routes plus QStash and GitHub Actions.
