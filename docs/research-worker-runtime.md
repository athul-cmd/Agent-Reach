# Research Worker Runtime

This document describes the background Python runtime for Content Research Studio.

For the full hosted deployment contract, use [research-deployment.md](./research-deployment.md).

## Purpose

The Python runtime owns:

1. scheduler heartbeat
2. source collection
3. clustering and ranking
4. style learning
5. idea generation
6. weekly digest publication

The deployment model is:

1. Vercel runs the frontend and Next.js server routes
2. Supabase provides Auth, Postgres, and Storage
3. Upstash QStash triggers the scheduler route
4. GitHub Actions executes claimed Python jobs

## Commands

Prepare configured storage:

```bash
agent-reach research storage prepare
```

Run the local worker fallback:

```bash
agent-reach research worker run
```

Pin the local worker fallback to one profile and override sleep:

```bash
agent-reach research worker run --profile-id <profile_id> --sleep-seconds 300
```

Inspect worker status:

```bash
agent-reach research worker status
```

Run verification:

```bash
agent-reach research verify storage
agent-reach research verify sources
agent-reach research verify all
```

## Required environment variables

At minimum:

```bash
AGENT_REACH_RESEARCH_API_ACCESS_TOKEN=...
AGENT_REACH_RESEARCH_DB_BACKEND=supabase
AGENT_REACH_RESEARCH_DB_DSN=postgresql://...
AGENT_REACH_RESEARCH_BLOB_BACKEND=supabase
AGENT_REACH_RESEARCH_BLOB_BUCKET=research-artifacts
AGENT_REACH_RESEARCH_BLOB_PREFIX=agent-reach/research
AGENT_REACH_RESEARCH_SUPABASE_URL=https://<project-ref>.supabase.co
AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY=...
AGENT_REACH_RESEARCH_SETTINGS_ENCRYPTION_KEY=...
AGENT_REACH_RESEARCH_SUPABASE_OWNER_USER_ID=<supabase-user-id>
```

Optional direct fallback for local/operator use:

```bash
OPENAI_API_KEY=...
```

The preferred path is:

1. user signs in through Supabase Auth
2. user saves OpenAI key in the app settings UI
3. frontend stores encrypted key metadata in Supabase
4. worker reads and decrypts that key server-side

## Runtime behavior

1. the default hosted path uses QStash plus GitHub Actions, not an always-on worker host
2. the local worker command remains available as a fallback and for local verification
3. job claims are leased in Postgres so retries can recover safely
4. Python execution reads and writes directly against Supabase-backed storage

## Local development

For local development:

1. use Supabase for auth and settings
2. use Supabase Postgres as the preferred database target
3. optionally keep a direct `OPENAI_API_KEY` env as a local fallback while bootstrapping

Use [research-local-setup.md](./research-local-setup.md) for the full local sequence.
