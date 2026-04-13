import "server-only"

import { redirect } from "next/navigation"
import { createServerSupabaseClient } from "@/lib/supabase/server"

type ResearchAuthState =
  | { kind: "authenticated" }
  | { kind: "anonymous" }
  | { kind: "env-missing" }
  | { kind: "error"; message: string }

function loginHref(nextPath: string): string {
  const params = new URLSearchParams({ next: nextPath })
  return `/research/login?${params.toString()}`
}

function loginHrefWithError(nextPath: string, error: string): string {
  const params = new URLSearchParams({ next: nextPath, error })
  return `/research/login?${params.toString()}`
}

async function readResearchAuthState(): Promise<ResearchAuthState> {
  try {
    const supabase = await createServerSupabaseClient()
    const {
      data: { user },
      error,
    } = await supabase.auth.getUser()

    if (error) {
      return { kind: "error", message: error.message }
    }

    return user ? { kind: "authenticated" } : { kind: "anonymous" }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Session check failed."
    if (message.includes("NEXT_PUBLIC_SUPABASE_URL") || message.includes("NEXT_PUBLIC_SUPABASE_ANON_KEY")) {
      return { kind: "env-missing" }
    }
    return { kind: "error", message }
  }
}

export async function requireResearchPageSession(nextPath: string): Promise<void> {
  const state = await readResearchAuthState()

  if (state.kind === "authenticated") {
    return
  }
  if (state.kind === "env-missing") {
    redirect(loginHrefWithError(nextPath, "supabase-env-missing"))
  }
  if (state.kind === "error") {
    redirect(loginHrefWithError(nextPath, "session-check-failed"))
  }
  redirect(loginHref(nextPath))
}

export async function redirectAuthenticatedResearchUser(destination = "/research"): Promise<void> {
  const state = await readResearchAuthState()

  if (state.kind === "authenticated") {
    redirect(destination)
  }
}
