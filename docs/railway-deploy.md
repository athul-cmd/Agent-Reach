# Optional Paid Upgrade: Deploy research API + worker on Railway

Railway is now an **optional paid upgrade path**, not the default architecture. Use it only if QStash plus GitHub Actions is no longer sufficient and you want an always-on Python API plus worker host. Next.js stays on Vercel; Supabase stays cloud-hosted.

## 1. Install the Railway CLI (required for Cursor MCP)

The **Railway MCP** in Cursor shells out to `railway`. If `railway --version` fails, install the CLI and log in:

```bash
# macOS (Homebrew)
brew install railway

railway login
```

Verify:

```bash
railway --version
railway whoami
```

`railway whoami` should print your Railway account after login. Until login succeeds, Cursor’s **Railway MCP** tools will report “Not logged in”.

After this, MCP actions like **list-projects**, **deploy**, and **set-variables** work from Cursor (they call the same CLI).

## 2. Create the project, services, and link the repo

### Option A — scripted (after `railway login`)

From the **repository root**:

```bash
cd /Users/athuldileep/Documents/Agent-Reach
chmod +x scripts/railway-bootstrap.sh
./scripts/railway-bootstrap.sh
```

This creates/links project **`agent-reach-research`**, runs `railway add` for **`research-api`** and **`research-worker`**, and prints the exact **start commands** and **deploy** commands. If a service already exists, you may see a harmless error; finish wiring in the Railway UI.

### Option B — manual

```bash
cd /Users/athuldileep/Documents/Agent-Reach
railway init -n agent-reach-research
```

Or create a project in the [Railway dashboard](https://railway.app), connect this GitHub repo, and run `railway link -p <project-id>` in the repo root.

### Headless / Cursor MCP without a browser

Create an **account token** in Railway (**Account → Tokens**), then:

```bash
export RAILWAY_API_TOKEN="your-token-here"
railway whoami
```

After that, `./scripts/railway-bootstrap.sh` and Cursor’s Railway MCP can run non-interactively. Do **not** commit the token; add it in your shell profile or Cursor’s environment only.

## 3. Two services, same repo root

In the Railway project, add **two** services that both use **this repo** and the **repo root** as the root directory (no `nodepad-main` here—Python lives at the root).

| Service name (suggested) | Start command | Health check |
|--------------------------|---------------|--------------|
| `research-api` | `agent-reach research serve --host 0.0.0.0 --port $PORT` | Path: `/health` |
| `research-worker` | `agent-reach research worker run` | None (not HTTP) |

**Important:** the API **must** bind to `0.0.0.0` and use Railway’s `PORT`. The default `127.0.0.1` is wrong on Railway.

**Build:** `railway.json` at the repo root sets:

`pip install -e '.[postgres,crypto]'`

so Postgres + encryption extras are installed for both services. If you need more extras later, extend that command in `railway.json`.

## 4. Environment variables (set on *both* services)

Use the same names as local Python setup (see [research-local-setup.md](./research-local-setup.md)). Typical set:

- `AGENT_REACH_RESEARCH_DB_BACKEND=supabase`
- `AGENT_REACH_RESEARCH_DB_DSN` — Postgres connection string (Supabase pooler or direct)
- `AGENT_REACH_RESEARCH_SUPABASE_URL`
- `AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY`
- `AGENT_REACH_RESEARCH_SUPABASE_OWNER_USER_ID` — if your deployment uses it
- `AGENT_REACH_RESEARCH_BLOB_BACKEND`, `AGENT_REACH_RESEARCH_BLOB_BUCKET`, `AGENT_REACH_RESEARCH_BLOB_PREFIX` — if using Storage
- `AGENT_REACH_RESEARCH_SETTINGS_ENCRYPTION_KEY` — same secret as Next `RESEARCH_SETTINGS_ENCRYPTION_KEY`
- `AGENT_REACH_RESEARCH_API_ACCESS_TOKEN` — shared secret; must match Next `RESEARCH_API_ACCESS_TOKEN`

Optional: `OPENAI_API_KEY` on the worker/API if you rely on env fallback instead of encrypted settings only.

In Cursor, after the CLI works, you can use MCP **set-variables** with `workspacePath` pointing at this repo.

## 5. Public URL for the API

For `research-api`, generate a public domain (Railway dashboard → service → **Networking → Generate domain**). Set your Vercel / Next env:

- `RESEARCH_API_BASE_URL=https://<your-railway-api-host>` (no trailing slash, or match your Next proxy code)
- `RESEARCH_API_ACCESS_TOKEN=<same as AGENT_REACH_RESEARCH_API_ACCESS_TOKEN>`

## 6. MCP quick reference (repo root as `workspacePath`)

- `check-railway-status` — CLI installed and logged in
- `list-projects` / `list-services` — see what exists
- `link-service` / `link-environment` — attach Cursor workspace to a service
- `set-variables` — `variables: ["KEY=value", ...]`
- `deploy` — `workspacePath` + optional `service`
- `generate-domain` — public URL for the linked API service

## 7. What we do *not* deploy on Railway

- **Next.js** (`nodepad-main/`) — deploy to Vercel (or another Node host).
- **Agent Reach CLI-only usage** (`doctor`, channels) — optional; not required for Research Studio.
