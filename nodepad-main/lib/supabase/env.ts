export function supabaseUrl(): string {
  return process.env.NEXT_PUBLIC_SUPABASE_URL || ""
}

export function supabaseAnonKey(): string {
  return process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""
}

export function assertSupabaseEnv() {
  const url = supabaseUrl()
  const anonKey = supabaseAnonKey()
  if (!url || !anonKey) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY.")
  }
  return { url, anonKey }
}
