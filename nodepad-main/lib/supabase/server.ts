import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"
import { assertSupabaseEnv } from "@/lib/supabase/env"

export async function createServerSupabaseClient() {
  const { url, anonKey } = assertSupabaseEnv()
  const cookieStore = await cookies()

  return createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet: Array<{ name: string; value: string; options?: Parameters<typeof cookieStore.set>[2] }>) {
        cookiesToSet.forEach(({ name, value, options }) => {
          cookieStore.set(name, value, options)
        })
      },
    },
  })
}
