import { createBrowserClient } from "@supabase/ssr"
import { assertSupabaseEnv } from "@/lib/supabase/env"

export function createBrowserSupabaseClient() {
  const { url, anonKey } = assertSupabaseEnv()
  return createBrowserClient(url, anonKey)
}
