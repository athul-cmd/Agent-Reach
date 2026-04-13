# Research Studio Local Setup

This document describes the current local development flow for Content Research Studio.

For the hosted production setup, use [research-deployment.md](./research-deployment.md).

## What runs locally

You need two required pieces plus one optional local fallback:

1. the Next.js frontend in `nodepad-main`
2. Supabase-backed Postgres and Storage
3. optional local Python execution for verification or fallback flows

Supabase is still used for auth and app settings even in local development.

### Auth model (no owner token)

Research routes are gated by **Supabase email/password** (`/research/login`), not a shared `RESEARCH_STUDIO_OWNER_TOKEN`. Next.js 16 uses a root [`nodepad-main/proxy.ts`](../nodepad-main/proxy.ts) file only (do **not** add `middleware.ts` alongside it — Next will crash on startup). That proxy refreshes the Supabase session cookie and protects `/research` (except `/research/login`), `/api/research/*`, and `/api/settings/*`. `/research/login` must stay **public** so the matcher does not redirect it to itself (that pattern caused **ERR_TOO_MANY_REDIRECTS** before the login path was excluded from “protected” pages).

### Repo root `package.json` (npm from `Agent-Reach/`)

The repository root includes a minimal `package.json` so **`npm run dev` from `Agent-Reach/`** runs the app inside `nodepad-main` (correct working directory for module resolution). Without it, npm walks up to **`$HOME`** if that directory has a `package.json`, which is confusing and wrong for this project. Do **not** use `npm run dev --prefix nodepad-main` from the repo root without changing into `nodepad-main` first — Turbopack can otherwise resolve imports against the wrong directory.

### Content Security Policy

`next.config.mjs` builds `connect-src` from **`NEXT_PUBLIC_SUPABASE_URL`** (that origin plus matching `wss://` for Realtime). If the URL is unset at build time, it falls back to `https://*.supabase.co` / `wss://*.supabase.co`. Without a valid Supabase entry in `connect-src`, browser sign-in fails.

## Progress vs still to do

**In place**

- Next.js app with `/research`, `/research/login` (Supabase), `/research/settings`, and direct server routes for dashboard reads/writes.
- Root `proxy.ts` for session refresh and route protection (Next.js 16; no separate `middleware.ts`).
- Python research API and worker CLI; optional Supabase-backed DB/blob and encrypted settings (see env above).
- SQL: apply `agent_reach/research/sql/postgres_schema.sql` then `nodepad-main/supabase/research_studio.sql` on Supabase (RLS on `research_user_settings`).

**Still required for a fully functional loop**

- Supabase **Auth** enabled (email/password); create a user and sign in.
- Python runtime env pointing at the same Supabase Postgres (or local SQLite for explicit dev-only fallback).
- `OPENAI_API_KEY` via **settings UI** (or env fallback) so style/idea jobs can call the model.
- Optional: install upstream CLIs (`mcporter`, `rdt`, `yt-dlp`, `twitter`) for real source collection.
- Production: schedule jobs through QStash and GitHub Actions; use the local worker only as a fallback (see `docs/research-deployment.md`).

## 1. Create the Python environment

From the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

If you want Postgres-backed storage locally:

```bash
.venv/bin/pip install -e '.[postgres]'
```

If you want the worker to decrypt OpenAI settings stored in Supabase:

```bash
.venv/bin/pip install -e '.[postgres,crypto]'
```

## 2. Create the frontend env file

Copy the example file:

```bash
cp nodepad-main/.env.example nodepad-main/.env.local
```

Fill in:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
RESEARCH_SETTINGS_ENCRYPTION_KEY=replace-with-a-long-random-secret
RESEARCH_API_ACCESS_TOKEN=replace-with-a-shared-backend-token
```

`RESEARCH_API_BASE_URL` is now optional and only needed if you still want to proxy legacy Python API endpoints during local migration.

## 3. Python environment variables

In the shell where you run the Python API and worker:

```bash
export AGENT_REACH_RESEARCH_API_ACCESS_TOKEN=replace-with-a-shared-backend-token
export AGENT_REACH_RESEARCH_DB_BACKEND=supabase
export AGENT_REACH_RESEARCH_DB_DSN=postgresql://...
export AGENT_REACH_RESEARCH_BLOB_BACKEND=supabase
export AGENT_REACH_RESEARCH_BLOB_BUCKET=research-artifacts
export AGENT_REACH_RESEARCH_BLOB_PREFIX=agent-reach/research
export AGENT_REACH_RESEARCH_SUPABASE_URL=https://<your-project-ref>.supabase.co
export AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY=replace-with-your-service-role-key
export AGENT_REACH_RESEARCH_SETTINGS_ENCRYPTION_KEY=replace-with-the-same-secret
export AGENT_REACH_RESEARCH_SUPABASE_OWNER_USER_ID=<supabase-user-id>
```

Optional direct fallback:

```bash
export OPENAI_API_KEY=...
```

The preferred path is to save the OpenAI key through the authenticated settings UI, not through shell env.

## 4. Apply the Supabase SQL

Before using the app, apply the SQL in:

```text
nodepad-main/supabase/research_studio.sql
```

That file creates the encrypted settings table and the required policies for the research frontend.

## 5. Install frontend dependencies

```bash
cd nodepad-main
npm install
```

## 6. Start the Python API

From the repo root:

```bash
.venv/bin/agent-reach research serve
```

Health check:

```bash
curl http://127.0.0.1:8877/health
```

## 7. Start the worker

From the repo root:

```bash
.venv/bin/agent-reach research worker run
```

Inspect runtime state:

```bash
.venv/bin/agent-reach research worker status
```

## 7b. One terminal: API + Next.js (lighter default)

Running **three separate terminals** does not reduce RAM versus one terminal; the same processes still run. To **avoid an extra Python process** while you iterate on the UI, skip the worker and run only the **research API** and **Next.js** together:

```bash
# from the repository root, after .venv exists and nodepad-main deps are installed
npm run dev:stack
```

This uses `concurrently` (`npx`, no extra install) with **`-k`**: **Ctrl+C stops both** the API and the web app.

- If Turbopack is hard on your machine: `npm run dev:stack:webpack`
- To include the **worker** as well (more CPU; scheduled jobs): `npm run dev:stack:full`

## 8. Start the frontend

From the **repository root** (recommended):

```bash
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Or from `nodepad-main`:

```bash
npm run dev -- --hostname 127.0.0.1 --port 3000
```

If the machine struggles with memory or CPU during dev (fan noise, system freeze), try webpack instead of the default Turbopack:

```bash
npm run dev:webpack -- --hostname 127.0.0.1 --port 3000
```

(from the repository root; or `cd nodepad-main` and `npm run dev:webpack -- ...`)

Use **one** dev server at a time; if port 3000 is already taken, stop the old process first (`lsof -i :3000` then `kill <pid>` on macOS/Linux).

Open:

```text
http://127.0.0.1:3000/research/login
```

## 9. First-use flow

1. create a Supabase account user with email/password
2. sign in to `/research/login`
3. open `/research/settings`
4. save the OpenAI key there
5. create the research profile there
6. return to `/research` and add writing samples
7. optionally import LinkedIn-style posts
8. run verification and refresh jobs

## 10. Source readiness

The dashboard will load without source CLIs, but collection quality depends on them.

Current adapters expect:

1. `mcporter` for Web/Exa
2. `rdt` for Reddit
3. `yt-dlp` for YouTube
4. `twitter` for X

Use:

```bash
.venv/bin/agent-reach research verify sources
```

For a live smoke check:

```bash
.venv/bin/agent-reach research verify sources --run-collect --limit 1
```
