export type {
  CreatorWatchPayload,
  OpenAISettingsPayload,
  ResearchDashboardData,
  ResearchProfileInput,
  SourceHealthPayload,
  SourceItemPayload,
  TopicClusterPayload,
  VerificationPayload,
  VerificationSourceCheckPayload,
} from "./research-types"

import type {
  OpenAISettingsPayload,
  ResearchDashboardData,
  ResearchProfileInput,
  VerificationPayload,
  VerificationSourceCheckPayload,
} from "./research-types"

function currentBrowserPath(): string {
  if (typeof window === "undefined") return "/research"
  return `${window.location.pathname}${window.location.search}`
}

function redirectToResearchLogin() {
  if (typeof window === "undefined") return
  const params = new URLSearchParams({ next: currentBrowserPath() })
  window.location.assign(`/research/login?${params.toString()}`)
}

const DIRECT_RESEARCH_API_BASE_URL = "managed://supabase"

async function postProxy(path: string, payload: object) {
  const response = await fetch(`/api/research${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  })
  if (response.status === 401) {
    redirectToResearchLogin()
    throw new Error("Research session expired.")
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(String(data?.error || `Request failed with status ${response.status}.`))
  }
  return data
}

export async function loadResearchDashboardClient(): Promise<ResearchDashboardData> {
  const response = await fetch("/api/research/api/dashboard", {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  })
  if (response.status === 401) {
    redirectToResearchLogin()
    throw new Error("Research session expired.")
  }
  const data = await response.json().catch(() => null)
  if (!response.ok || !data) {
    throw new Error(String(data?.error || `Dashboard request failed with status ${response.status}.`))
  }
  return {
    available: true,
    apiBaseUrl: data.apiBaseUrl || DIRECT_RESEARCH_API_BASE_URL,
    error: null,
    generated_at: data.generated_at ?? null,
    system_health: data.system_health ?? null,
    profile: data.profile ?? null,
    style_profile: data.style_profile ?? null,
    report: data.report ?? null,
    source_items: data.source_items ?? [],
    clusters: data.clusters ?? [],
    ideas: data.ideas ?? [],
    creators: data.creators ?? [],
    active_refresh: data.active_refresh ?? null,
    refresh_jobs: data.refresh_jobs ?? [],
    job_events: data.job_events ?? [],
    jobs: data.jobs ?? [],
    metrics: data.metrics ?? {
      source_item_count: 0,
      cluster_count: 0,
      idea_count: 0,
      creator_count: 0,
    },
  }
}

export async function saveResearchProfile(input: ResearchProfileInput) {
  return postProxy("/api/profile", input)
}

export async function addWritingSample(payload: {
  profile_id?: string
  title: string
  raw_text: string
  source_type?: string
}) {
  return postProxy("/api/profile/writing-samples", payload)
}

export async function importLinkedInPosts(payload: {
  profile_id?: string
  posts: { title?: string; text: string; url?: string }[]
}) {
  return postProxy("/api/profile/linkedin-import", payload)
}

export async function runManualJob(payload: { profile_id?: string; job: string }) {
  return postProxy("/api/runs/manual", payload)
}

export async function saveIdea(payload: { profile_id?: string; idea_id: string }) {
  return postProxy(`/api/ideas/${payload.idea_id}/save`, { profile_id: payload.profile_id })
}

export async function discardIdea(payload: { profile_id?: string; idea_id: string; note?: string }) {
  return postProxy(`/api/ideas/${payload.idea_id}/discard`, {
    profile_id: payload.profile_id,
    note: payload.note || "",
  })
}

export async function sendIdeaFeedback(payload: {
  profile_id?: string
  idea_id: string
  note: string
}) {
  return postProxy(`/api/ideas/${payload.idea_id}/feedback`, {
    profile_id: payload.profile_id,
    note: payload.note,
  })
}

async function createBrowserSupabaseClient() {
  const module = await import("@/lib/supabase/browser")
  return module.createBrowserSupabaseClient()
}

export async function signInResearchUser(email: string, password: string) {
  const supabase = await createBrowserSupabaseClient()
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })
  if (error) {
    throw new Error(error.message)
  }
  return data
}

export async function signUpResearchUser(email: string, password: string) {
  const supabase = await createBrowserSupabaseClient()
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
  })
  if (error) {
    throw new Error(error.message)
  }
  return data
}

export async function signOutResearchUser() {
  const supabase = await createBrowserSupabaseClient()
  const { error } = await supabase.auth.signOut()
  if (error) {
    throw new Error(error.message)
  }
}

export async function loadOpenAISettings(): Promise<OpenAISettingsPayload> {
  const response = await fetch("/api/settings/openai", {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  })
  if (response.status === 401) {
    redirectToResearchLogin()
    throw new Error("Research session expired.")
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(String(data?.error || `Settings request failed with status ${response.status}.`))
  }
  return data as OpenAISettingsPayload
}

export async function saveOpenAISettings(apiKey: string): Promise<OpenAISettingsPayload> {
  const response = await fetch("/api/settings/openai", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ apiKey }),
  })
  if (response.status === 401) {
    redirectToResearchLogin()
    throw new Error("Research session expired.")
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(String(data?.error || `Settings save failed with status ${response.status}.`))
  }
  return data as OpenAISettingsPayload
}

export async function deleteOpenAISettings(): Promise<OpenAISettingsPayload> {
  const response = await fetch("/api/settings/openai", {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  })
  if (response.status === 401) {
    redirectToResearchLogin()
    throw new Error("Research session expired.")
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(String(data?.error || `Settings delete failed with status ${response.status}.`))
  }
  return data as OpenAISettingsPayload
}

export async function runSystemVerification(payload: {
  profile_id?: string
  mode: "storage" | "sources" | "all"
  run_collect?: boolean
  limit?: number
}): Promise<VerificationPayload> {
  const data = await postProxy("/api/system/verify", {
    profile_id: payload.profile_id,
    mode: payload.mode,
    run_collect: Boolean(payload.run_collect),
    limit: payload.limit ?? 1,
  })
  const verification = data.verification as VerificationPayload
  const raw = data.verification as VerificationPayload & {
    run_collect?: boolean
    checks?: VerificationSourceCheckPayload[]
  }
  if (verification.database || verification.blob_store) {
    verification.storage = {
      generated_at: verification.generated_at,
      database: verification.database,
      blob_store: verification.blob_store,
    }
  }
  if (Array.isArray(raw.checks)) {
    verification.sources = {
      generated_at: verification.generated_at,
      status: verification.status,
      run_collect: Boolean(raw.run_collect),
      checks: raw.checks,
    }
  }
  return verification
}
