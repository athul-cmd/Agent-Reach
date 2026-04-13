import "server-only"

import { redirect } from "next/navigation"
import { createServerSupabaseClient } from "@/lib/supabase/server"

function loginHref(nextPath: string): string {
  const params = new URLSearchParams({ next: nextPath })
  return `/research/login?${params.toString()}`
}

export async function requireResearchPageSession(nextPath: string): Promise<void> {
  const supabase = await createServerSupabaseClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect(loginHref(nextPath))
  }
}

export async function redirectAuthenticatedResearchUser(destination = "/research"): Promise<void> {
  const supabase = await createServerSupabaseClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (user) {
    redirect(destination)
  }
}
