"use client"

import Link from "next/link"
import { useEffect } from "react"
import { AlertTriangle, RefreshCw, RadioTower } from "lucide-react"

export default function ResearchError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Research route render error", error)
  }, [error])

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#030303] px-6 text-foreground">
      <div className="w-full max-w-2xl rounded-sm border border-border/60 bg-card/60 p-6 shadow-2xl shadow-black/30 backdrop-blur-md">
        <div className="mb-3 flex items-center gap-2">
          <RadioTower className="h-4 w-4 text-primary" />
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.24em] text-primary/80">
            Research Studio
          </p>
        </div>
        <div className="mb-4 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-300" />
          <h1 className="text-xl font-semibold tracking-tight">Could not render the research page</h1>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          The server hit an error while preparing this page. Use the settings page to confirm Supabase
          env, profile data, and OpenAI settings are configured.
        </p>
        {error.digest && (
          <p className="mt-4 rounded-sm border border-border/50 bg-black/20 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Digest: {error.digest}
          </p>
        )}
        <div className="mt-6 flex flex-wrap gap-2">
          <button
            onClick={() => reset()}
            className="inline-flex items-center gap-2 rounded-sm border border-primary/60 bg-primary/15 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
          <Link
            href="/research/settings"
            className="inline-flex items-center gap-2 rounded-sm border border-border/60 bg-card/40 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
          >
            <RadioTower className="h-3.5 w-3.5" />
            Open Settings
          </Link>
          <Link
            href="/research/login"
            className="inline-flex items-center gap-2 rounded-sm border border-border/60 bg-card/40 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
          >
            Back To Login
          </Link>
        </div>
      </div>
    </main>
  )
}
