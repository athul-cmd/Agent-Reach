# Research Studio Frontend

This app is the frontend for Content Research Studio.

It is no longer the original browser-local Nodepad product. The current architecture is:

1. Next.js frontend hosted on Vercel
2. Supabase Auth for email/password login
3. Supabase-backed app settings for encrypted OpenAI key storage
4. direct Next.js server routes for dashboard reads and user-triggered writes
5. QStash-triggered scheduling plus GitHub Actions for Python job execution

The frontend still reuses the Nodepad interaction model and shared spatial components, but it no longer uses:

1. browser `localStorage` as the product database
2. browser-held model provider keys
3. direct client-to-provider AI calls
4. owner-token login

## Local Setup

Use [docs/research-local-setup.md](../docs/research-local-setup.md) as the setup guide (from the repository root).
Use [docs/research-deployment.md](../docs/research-deployment.md) for the hosted Vercel + Supabase + QStash + GitHub Actions deployment path.

For Vercel, this app must be deployed with the project `Root Directory` set to `nodepad-main`.

At minimum, local frontend development needs these env vars in `nodepad-main/.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
RESEARCH_SETTINGS_ENCRYPTION_KEY=...
RESEARCH_API_ACCESS_TOKEN=...
```

`RESEARCH_API_BASE_URL` is optional and fallback-only. The standard dashboard path reads directly from Supabase through Next.js server routes.

Then start the frontend:

```bash
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open:

```text
http://127.0.0.1:3000/research/login
```

## Notes

1. The browser never stores the OpenAI key as runtime truth.
2. The dashboard is protected by Supabase Auth.
3. Profile setup and OpenAI configuration live at `/research/settings`.
4. Raw artifacts and snapshot exports are intended to use Supabase Storage from the Python backend.
5. The Python runtime is now a background executor, not the normal dashboard read path.
