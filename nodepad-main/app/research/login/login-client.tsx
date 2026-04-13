"use client"

import { FormEvent, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { KeyRound, Mail, RadioTower } from "lucide-react"
import { signInResearchUser, signUpResearchUser } from "@/lib/research-api"

type AuthMode = "signin" | "signup"

export function ResearchLoginClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const nextPath = useMemo(() => searchParams.get("next") || "/research", [searchParams])
  const envError = useMemo(
    () => searchParams.get("error") === "supabase-env-missing",
    [searchParams],
  )
  const [mode, setMode] = useState<AuthMode>("signin")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setStatus(null)
    try {
      if (mode === "signin") {
        await signInResearchUser(email, password)
        router.replace(nextPath)
        router.refresh()
      } else {
        const result = await signUpResearchUser(email, password)
        if (result.session) {
          router.replace(nextPath)
          router.refresh()
        } else {
          setStatus("Account created. Confirm the email if your Supabase project requires email verification.")
        }
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Authentication failed.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#030303] px-6 text-foreground">
      <div className="w-full max-w-md rounded-sm border border-border/60 bg-card/60 p-6 shadow-2xl shadow-black/30 backdrop-blur-md">
        <div className="mb-6">
          <div className="mb-2 flex items-center gap-2">
            <RadioTower className="h-4 w-4 text-primary" />
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.24em] text-primary/80">
              Research Studio
            </p>
          </div>
          <h1 className="text-xl font-semibold tracking-tight">{mode === "signin" ? "Sign In" : "Create Account"}</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Use Supabase email/password auth to unlock the private research dashboard.
          </p>
          {envError && (
            <p className="mt-3 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive/90">
              Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY in the frontend environment.
            </p>
          )}
        </div>

        <div className="mb-4 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setMode("signin")}
            className={`rounded-sm border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] ${
              mode === "signin"
                ? "border-primary/60 bg-primary/15 text-primary"
                : "border-border/60 bg-black/30 text-muted-foreground"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => setMode("signup")}
            className={`rounded-sm border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] ${
              mode === "signup"
                ? "border-primary/60 bg-primary/15 text-primary"
                : "border-border/60 bg-black/30 text-muted-foreground"
            }`}
          >
            Sign Up
          </button>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-foreground/60">
              Email
            </span>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                autoFocus
                className="w-full rounded-sm border border-border/60 bg-black/30 py-2 pl-10 pr-3 text-sm outline-none transition-colors focus:border-primary/60"
              />
            </div>
          </label>

          <label className="block">
            <span className="mb-2 block font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-foreground/60">
              Password
            </span>
            <div className="relative">
              <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Your password"
                className="w-full rounded-sm border border-border/60 bg-black/30 py-2 pl-10 pr-3 text-sm outline-none transition-colors focus:border-primary/60"
              />
            </div>
          </label>

          {status && (
            <p className="rounded-sm border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary/90">
              {status}
            </p>
          )}
          {error && (
            <p className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive/90">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !email.trim() || !password.trim()}
            className="w-full rounded-sm border border-primary/60 bg-primary/15 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary disabled:opacity-50"
          >
            {busy ? "Working" : mode === "signin" ? "Sign In" : "Create Account"}
          </button>
        </form>
      </div>
    </main>
  )
}
