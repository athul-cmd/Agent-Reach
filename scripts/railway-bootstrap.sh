#!/usr/bin/env bash
# Create/link a Railway project and add research-api + research-worker services.
# Prerequisite: `brew install railway` and `railway login` (or RAILWAY_API_TOKEN).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RAILWAY="${RAILWAY_CLI:-/opt/homebrew/bin/railway}"
if ! command -v railway >/dev/null 2>&1; then
  if [[ -x "$RAILWAY" ]]; then
    export PATH="/opt/homebrew/bin:$PATH"
  else
    echo "Install the Railway CLI: brew install railway"
    exit 1
  fi
fi

if ! railway whoami >/dev/null 2>&1; then
  echo "Not logged in. Run in your terminal:"
  echo "  railway login"
  echo ""
  echo "For CI or headless setups, set an account token (see https://docs.railway.com/guides/cli):"
  echo "  export RAILWAY_API_TOKEN=\"<token from Railway dashboard → Account → Tokens>\""
  exit 1
fi

echo "Logged in as: $(railway whoami)"

if ! railway status >/dev/null 2>&1; then
  echo "No project linked in $ROOT — creating project agent-reach-research..."
  railway init -n "agent-reach-research"
else
  echo "Project already linked:"
  railway status
fi

echo "Adding services (ok if they already exist — you may see an error; then use the dashboard to rename/duplicate)."
railway add -s research-api  || true
railway add -s research-worker || true

echo ""
echo "Next steps (Railway dashboard, each service → Settings):"
echo "  research-api start:    agent-reach research serve --host 0.0.0.0 --port \$PORT"
echo "  research-api health:   /health"
echo "  research-worker start: agent-reach research worker run"
echo ""
echo "Shared build is in railway.json (pip install -e '.[postgres,crypto]')."
echo "Set the same Supabase/env vars on BOTH services (see docs/railway-deploy.md)."
echo "Generate a public domain for research-api, then set Vercel RESEARCH_API_BASE_URL."
echo ""
echo "Deploy API:"
echo "  railway service link research-api   # if not already linked"
echo "  railway up -s research-api -d"
echo ""
echo "Deploy worker (from same repo, switch linked service):"
echo "  railway service link research-worker"
echo "  railway up -s research-worker -d"
