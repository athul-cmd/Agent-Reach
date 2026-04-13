import "server-only"

import { randomUUID } from "node:crypto"
import { createClient, type SupabaseClient } from "@supabase/supabase-js"
import type {
  CreatorWatchPayload,
  JobRunPayload,
  ResearchDashboardData,
  ResearchProfileInput,
  ResearchProfilePayload,
  SourceHealthPayload,
  SourceItemPayload,
  StyleProfilePayload,
  SystemHealthPayload,
  TopicClusterPayload,
  VerificationPayload,
  VerificationSourceCheckPayload,
  WeeklyReportPayload,
  WorkerHealthPayload,
} from "@/lib/research-types"
import {
  buildGitHubDispatchRequest,
  DIRECT_RESEARCH_API_BASE_URL,
  gitHubDispatchErrorMessage,
  githubDispatchConfigured,
  qstashConfigured,
} from "@/lib/research-runtime"
import { createServerSupabaseClient } from "@/lib/supabase/server"

type ResearchAdminClient = SupabaseClient

type UserFeedbackEventType = "save" | "discard" | "feedback"

type JobType =
  | "collect_sources"
  | "discover_creators"
  | "refresh_style_profile"
  | "cluster_items"
  | "rank_topics"
  | "generate_ideas"
  | "publish_weekly_digest"

type JobStatus = "pending" | "running" | "succeeded" | "failed" | "interrupted"

type ResearchProfileRow = {
  id: string
  name: string
  persona_brief: string
  niche_definition: string
  must_track_topics: string[] | null
  excluded_topics: string[] | null
  target_audience: string
  desired_formats: string[] | null
  status: string
  created_at: string
  updated_at: string
}

type StyleProfileRow = {
  id: string
  research_profile_id: string
  tone_markers: string[] | null
  hook_patterns: string[] | null
  structure_patterns: string[] | null
  preferred_topics: string[] | null
  avoided_topics: string[] | null
  evidence_preferences: string[] | null
  embedding_version: string
  raw_summary: string
  generated_at: string
}

type SourceItemRow = {
  id: string
  research_profile_id: string
  source: string
  external_id: string
  canonical_url: string
  author_name: string
  published_at: string
  title: string
  body_text: string
  engagement_json: Record<string, unknown> | null
  raw_blob_url: string
  health_status: string
  source_query: string
  created_at: string
}

type TopicClusterRow = {
  id: string
  research_profile_id: string
  cluster_label: string
  cluster_summary: string
  representative_terms: string[] | null
  supporting_item_ids: string[] | null
  source_family_count: number
  freshness_score: number
  cluster_key: string
  final_score: number
  score_components: Record<string, number> | null
  rank_snapshot_at: string
}

type IdeaCardRow = {
  id: string
  research_profile_id: string
  topic_cluster_id: string
  headline: string
  hook: string
  why_now: string
  outline_md: string
  evidence_item_ids: string[] | null
  final_score: number
  status: string
  generated_at: string
}

type CreatorWatchRow = {
  id: string
  research_profile_id: string
  source: string
  creator_external_id: string
  creator_name: string
  creator_url: string
  watch_reason: string
  watch_score: number
  status: string
  updated_at: string
}

type WeeklyReportRow = {
  id: string
  research_profile_id: string
  report_period_start: string
  report_period_end: string
  top_idea_ids: string[] | null
  top_creator_ids: string[] | null
  summary_md: string
  published_at: string
}

type JobRunRow = {
  id: string
  research_profile_id: string
  job_type: JobType
  status: JobStatus
  scheduled_for: string
  started_at: string | null
  finished_at: string | null
  attempt_count: number
  input_snapshot: Record<string, unknown> | null
  error_summary: string
  next_run_at: string | null
  heartbeat_at: string | null
  lease_token: string
  lease_owner: string
  lease_expires_at: string | null
  dispatched_at: string | null
}

const COLLECTION_INTERVAL_MS = 4 * 60 * 60 * 1000
const DEFAULT_DAILY_HOUR_UTC = 6
const DEFAULT_WEEKLY_WEEKDAY_UTC = 0
const DEFAULT_WEEKLY_HOUR_UTC = 8
const RESEARCH_JOB_TYPES: JobType[] = [
  "collect_sources",
  "discover_creators",
  "refresh_style_profile",
  "cluster_items",
  "rank_topics",
  "generate_ideas",
  "publish_weekly_digest",
]

function supabaseServiceRoleKey(): string {
  return (
    process.env.AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    ""
  )
}

function supabaseUrl(): string {
  return process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.AGENT_REACH_RESEARCH_SUPABASE_URL || ""
}

function assertResearchAdminEnv() {
  const url = supabaseUrl()
  const serviceRoleKey = supabaseServiceRoleKey()
  if (!url || !serviceRoleKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL and AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY/SUPABASE_SERVICE_ROLE_KEY.",
    )
  }
  return { url, serviceRoleKey }
}

function createResearchAdminClient(): ResearchAdminClient {
  const { url, serviceRoleKey } = assertResearchAdminEnv()
  return createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  })
}

async function requireResearchUser() {
  const supabase = await createServerSupabaseClient()
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser()
  if (error) {
    throw new Error(error.message)
  }
  if (!user) {
    throw new Error("Unauthorized.")
  }
  return user
}

function nowIso(): string {
  return new Date().toISOString()
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item)).filter(Boolean)
}

function asScoreMap(value: unknown): Record<string, number> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {}
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, Number(item) || 0]),
  )
}

function profilePayload(row: ResearchProfileRow | null): ResearchProfilePayload | null {
  if (!row) return null
  return {
    id: row.id,
    name: row.name,
    persona_brief: row.persona_brief,
    niche_definition: row.niche_definition,
    must_track_topics: asStringArray(row.must_track_topics),
    excluded_topics: asStringArray(row.excluded_topics),
    target_audience: row.target_audience || "",
    desired_formats: asStringArray(row.desired_formats),
    status: row.status,
    created_at: row.created_at,
    updated_at: row.updated_at,
  }
}

function styleProfilePayload(row: StyleProfileRow | null): StyleProfilePayload | null {
  if (!row) return null
  return {
    id: row.id,
    research_profile_id: row.research_profile_id,
    tone_markers: asStringArray(row.tone_markers),
    hook_patterns: asStringArray(row.hook_patterns),
    structure_patterns: asStringArray(row.structure_patterns),
    preferred_topics: asStringArray(row.preferred_topics),
    avoided_topics: asStringArray(row.avoided_topics),
    evidence_preferences: asStringArray(row.evidence_preferences),
    embedding_version: row.embedding_version,
    raw_summary: row.raw_summary,
    generated_at: row.generated_at,
  }
}

function sourceItemPayload(row: SourceItemRow): SourceItemPayload {
  return {
    id: row.id,
    research_profile_id: row.research_profile_id,
    source: row.source,
    external_id: row.external_id,
    canonical_url: row.canonical_url,
    author_name: row.author_name,
    published_at: row.published_at,
    title: row.title,
    body_text: row.body_text,
    engagement: row.engagement_json || {},
    raw_blob_url: row.raw_blob_url,
    health_status: row.health_status,
    source_query: row.source_query,
    created_at: row.created_at,
  }
}

function clusterPayload(row: TopicClusterRow): TopicClusterPayload {
  return {
    id: row.id,
    research_profile_id: row.research_profile_id,
    cluster_label: row.cluster_label,
    cluster_summary: row.cluster_summary,
    representative_terms: asStringArray(row.representative_terms),
    supporting_item_ids: asStringArray(row.supporting_item_ids),
    source_family_count: Number(row.source_family_count) || 0,
    freshness_score: Number(row.freshness_score) || 0,
    cluster_key: row.cluster_key,
    final_score: Number(row.final_score) || 0,
    score_components: asScoreMap(row.score_components),
    rank_snapshot_at: row.rank_snapshot_at,
  }
}

function ideaPayload(row: IdeaCardRow) {
  return {
    id: row.id,
    research_profile_id: row.research_profile_id,
    topic_cluster_id: row.topic_cluster_id,
    headline: row.headline,
    hook: row.hook,
    why_now: row.why_now,
    outline_md: row.outline_md,
    evidence_item_ids: asStringArray(row.evidence_item_ids),
    final_score: Number(row.final_score) || 0,
    status: row.status,
    generated_at: row.generated_at,
  }
}

function creatorPayload(row: CreatorWatchRow): CreatorWatchPayload {
  return {
    id: row.id,
    research_profile_id: row.research_profile_id,
    source: row.source,
    creator_external_id: row.creator_external_id,
    creator_name: row.creator_name,
    creator_url: row.creator_url,
    watch_reason: row.watch_reason,
    watch_score: Number(row.watch_score) || 0,
    status: row.status,
    updated_at: row.updated_at,
  }
}

function reportPayload(row: WeeklyReportRow | null): WeeklyReportPayload | null {
  if (!row) return null
  return {
    id: row.id,
    research_profile_id: row.research_profile_id,
    report_period_start: row.report_period_start,
    report_period_end: row.report_period_end,
    top_idea_ids: asStringArray(row.top_idea_ids),
    top_creator_ids: asStringArray(row.top_creator_ids),
    summary_md: row.summary_md,
    published_at: row.published_at,
  }
}

function jobPayload(row: JobRunRow): JobRunPayload {
  return {
    id: row.id,
    research_profile_id: row.research_profile_id,
    job_type: row.job_type,
    status: row.status,
    scheduled_for: row.scheduled_for,
    started_at: row.started_at,
    finished_at: row.finished_at,
    attempt_count: Number(row.attempt_count) || 0,
    input_snapshot: row.input_snapshot || {},
    error_summary: row.error_summary || "",
    next_run_at: row.next_run_at,
    heartbeat_at: row.heartbeat_at,
  }
}

function parseDate(value: string | null | undefined): number {
  if (!value) return 0
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function buildSourceHealth(items: SourceItemPayload[]): SourceHealthPayload[] {
  const grouped = new Map<string, SourceItemPayload[]>()
  for (const item of items) {
    const bucket = grouped.get(item.source) || []
    bucket.push(item)
    grouped.set(item.source, bucket)
  }
  return [...grouped.entries()].map(([source, sourceItems]) => {
    const latest = sourceItems.sort((a, b) => parseDate(b.published_at) - parseDate(a.published_at))[0]
    const ageMs = latest ? Date.now() - parseDate(latest.published_at) : Infinity
    return {
      source,
      status: latest?.health_status || "unknown",
      available: true,
      hint: "",
      item_count: sourceItems.length,
      latest_published_at: latest?.published_at || null,
      latest_health_status: latest?.health_status || null,
      stale: ageMs > 2 * 24 * 60 * 60 * 1000,
    }
  })
}

function buildWorkerHealth(jobs: JobRunPayload[]): WorkerHealthPayload {
  const running = jobs.find((job) => job.status === "running")
  const latest = jobs[0] || null
  const staleRunning =
    running && running.heartbeat_at ? Date.now() - parseDate(running.heartbeat_at) > 30 * 60 * 1000 : false
  if (staleRunning) {
    return {
      status: "degraded",
      state: "stalled",
      note: "A leased background job has not updated recently.",
      stale: true,
      last_update_at: running?.heartbeat_at || null,
      tick_count: 0,
      active_profile_id: running?.research_profile_id || null,
      last_result: null,
      last_error: running?.error_summary || null,
    }
  }
  return {
    status: "ok",
    state: running ? "running" : "scheduled",
    note: running
      ? "Jobs are executing through GitHub Actions."
      : "Jobs are scheduled via QStash and executed via GitHub Actions.",
    stale: false,
    last_update_at: running?.heartbeat_at || latest?.finished_at || latest?.scheduled_for || null,
    tick_count: 0,
    active_profile_id: running?.research_profile_id || latest?.research_profile_id || null,
    last_result: null,
    last_error: latest?.status === "failed" ? latest.error_summary : null,
  }
}

function buildSystemHealth(
  jobs: JobRunPayload[],
  sourceHealth: SourceHealthPayload[],
): SystemHealthPayload {
  const failedJobCount = jobs.filter((job) => job.status === "failed").length
  const pendingJobCount = jobs.filter((job) => job.status === "pending").length
  const worker = buildWorkerHealth(jobs)
  const sourceDegraded = sourceHealth.some((source) => source.status !== "ok" || source.stale)
  const overallStatus = worker.status !== "ok" || failedJobCount > 0 || sourceDegraded ? "degraded" : "ok"
  return {
    generated_at: nowIso(),
    status: overallStatus,
    worker,
    jobs: {
      status: failedJobCount > 0 ? "degraded" : "ok",
      latest_jobs: jobs.slice(0, 12).map((job) => ({
        job_type: job.job_type,
        status: job.status,
        scheduled_for: job.scheduled_for,
        finished_at: job.finished_at,
        error_summary: job.error_summary,
      })),
      failed_job_count: failedJobCount,
      pending_job_count: pendingJobCount,
    },
    sources: sourceHealth,
    storage: {
      db_backend: "supabase",
      blob_backend: "supabase",
      scheduler: "qstash+github-actions",
    },
  }
}

function emptyDashboard(error: string | null): ResearchDashboardData {
  return {
    available: false,
    apiBaseUrl: DIRECT_RESEARCH_API_BASE_URL,
    error,
    generated_at: null,
    system_health: null,
    profile: null,
    style_profile: null,
    report: null,
    source_items: [],
    clusters: [],
    ideas: [],
    creators: [],
    jobs: [],
    metrics: {
      source_item_count: 0,
      cluster_count: 0,
      idea_count: 0,
      creator_count: 0,
    },
  }
}

async function fetchLatestProfile(admin: ResearchAdminClient): Promise<ResearchProfileRow | null> {
  const { data, error } = await admin
    .from("research_profiles")
    .select("*")
    .order("updated_at", { ascending: false })
    .limit(1)
    .maybeSingle()
  if (error) throw new Error(error.message)
  return (data as ResearchProfileRow | null) || null
}

async function fetchProfileById(
  admin: ResearchAdminClient,
  profileId: string,
): Promise<ResearchProfileRow | null> {
  const { data, error } = await admin.from("research_profiles").select("*").eq("id", profileId).maybeSingle()
  if (error) throw new Error(error.message)
  return (data as ResearchProfileRow | null) || null
}

async function resolveProfile(
  admin: ResearchAdminClient,
  profileId?: string | null,
): Promise<ResearchProfileRow | null> {
  if (profileId) return fetchProfileById(admin, profileId)
  return fetchLatestProfile(admin)
}

function requireProfile(
  profile: ResearchProfileRow | null,
): asserts profile is ResearchProfileRow {
  if (!profile) {
    throw new Error("No active research profile.")
  }
}

export async function loadResearchDashboardServer(): Promise<ResearchDashboardData> {
  try {
    await requireResearchUser()
    const admin = createResearchAdminClient()
    const profile = await fetchLatestProfile(admin)
    if (!profile) {
      return {
        ...emptyDashboard(null),
        available: true,
        generated_at: nowIso(),
        system_health: buildSystemHealth([], []),
      }
    }

    const [styleProfileResult, reportResult, sourceItemsResult, clustersResult, ideasResult, creatorsResult, jobsResult] =
      await Promise.all([
        admin
          .from("style_profiles")
          .select("*")
          .eq("research_profile_id", profile.id)
          .order("generated_at", { ascending: false })
          .limit(1)
          .maybeSingle(),
        admin
          .from("weekly_reports")
          .select("*")
          .eq("research_profile_id", profile.id)
          .order("published_at", { ascending: false })
          .limit(1)
          .maybeSingle(),
        admin
          .from("source_items")
          .select("*")
          .eq("research_profile_id", profile.id)
          .order("published_at", { ascending: false })
          .limit(50),
        admin
          .from("topic_clusters")
          .select("*")
          .eq("research_profile_id", profile.id)
          .order("final_score", { ascending: false })
          .order("freshness_score", { ascending: false })
          .limit(25),
        admin
          .from("idea_cards")
          .select("*")
          .eq("research_profile_id", profile.id)
          .order("final_score", { ascending: false })
          .order("generated_at", { ascending: false })
          .limit(25),
        admin
          .from("creator_watchlists")
          .select("*")
          .eq("research_profile_id", profile.id)
          .order("watch_score", { ascending: false })
          .order("updated_at", { ascending: false })
          .limit(12),
        admin
          .from("job_runs")
          .select("*")
          .eq("research_profile_id", profile.id)
          .order("scheduled_for", { ascending: false })
          .limit(12),
      ])

    for (const result of [
      styleProfileResult,
      reportResult,
      sourceItemsResult,
      clustersResult,
      ideasResult,
      creatorsResult,
      jobsResult,
    ]) {
      if (result.error) {
        throw new Error(result.error.message)
      }
    }

    const sourceItems = ((sourceItemsResult.data || []) as SourceItemRow[]).map(sourceItemPayload)
    const clusters = ((clustersResult.data || []) as TopicClusterRow[]).map(clusterPayload)
    const ideas = ((ideasResult.data || []) as IdeaCardRow[]).map(ideaPayload)
    const creators = ((creatorsResult.data || []) as CreatorWatchRow[]).map(creatorPayload)
    const jobs = ((jobsResult.data || []) as JobRunRow[]).map(jobPayload)
    const sourceHealth = buildSourceHealth(sourceItems)

    return {
      available: true,
      apiBaseUrl: DIRECT_RESEARCH_API_BASE_URL,
      error: null,
      generated_at: nowIso(),
      system_health: buildSystemHealth(jobs, sourceHealth),
      profile: profilePayload(profile),
      style_profile: styleProfilePayload((styleProfileResult.data as StyleProfileRow | null) || null),
      report: reportPayload((reportResult.data as WeeklyReportRow | null) || null),
      source_items: sourceItems,
      clusters,
      ideas,
      creators,
      jobs,
      metrics: {
        source_item_count: sourceItems.length,
        cluster_count: clusters.length,
        idea_count: ideas.length,
        creator_count: creators.length,
      },
    }
  } catch (error) {
    return emptyDashboard(error instanceof Error ? error.message : "Could not load dashboard.")
  }
}

export async function upsertResearchProfileServer(input: ResearchProfileInput) {
  await requireResearchUser()
  const admin = createResearchAdminClient()
  const current = await fetchLatestProfile(admin)
  const timestamp = nowIso()
  const payload = {
    id: current?.id || `profile_${randomUUID().replace(/-/g, "").slice(0, 12)}`,
    name: String(input.name || "").trim(),
    persona_brief: String(input.persona_brief || "").trim(),
    niche_definition: String(input.niche_definition || "").trim(),
    target_audience: String(input.target_audience || "").trim(),
    must_track_topics: input.must_track_topics || [],
    excluded_topics: input.excluded_topics || [],
    desired_formats: input.desired_formats || [],
    status: current?.status || "active",
    created_at: current?.created_at || timestamp,
    updated_at: timestamp,
  }
  if (!payload.name || !payload.persona_brief || !payload.niche_definition) {
    throw new Error("Profile requires name, persona_brief, and niche_definition.")
  }
  const { error } = await admin.from("research_profiles").upsert(payload, { onConflict: "id" })
  if (error) throw new Error(error.message)
  return { profile: profilePayload(payload as ResearchProfileRow) }
}

type WritingSampleInput = {
  title: string
  raw_text: string
  source_type?: string
  raw_blob_url?: string
  language?: string
}

async function insertWritingSamples(
  profileId: string,
  samples: WritingSampleInput[],
  sourceTypeFallback: string,
) {
  const admin = createResearchAdminClient()
  const timestamp = nowIso()
  const rows = samples
    .map((sample) => ({
      id: `sample_${randomUUID().replace(/-/g, "").slice(0, 12)}`,
      research_profile_id: profileId,
      source_type: String(sample.source_type || sourceTypeFallback || "uploaded"),
      title: String(sample.title || "").trim(),
      raw_text: String(sample.raw_text || "").trim(),
      raw_blob_url: String(sample.raw_blob_url || ""),
      language: String(sample.language || "en"),
      created_at: timestamp,
    }))
    .filter((sample) => sample.title && sample.raw_text)
  if (!rows.length) {
    throw new Error("No valid writing samples found in request.")
  }
  const { error } = await admin.from("writing_samples").insert(rows)
  if (error) throw new Error(error.message)
  return {
    added: rows.length,
    samples: rows.map((row) => ({
      ...row,
      created_at: row.created_at,
    })),
  }
}

export async function addWritingSamplesServer(payload: {
  profile_id?: string
  title?: string
  raw_text?: string
  source_type?: string
  samples?: WritingSampleInput[]
}) {
  await requireResearchUser()
  const admin = createResearchAdminClient()
  const profile = await resolveProfile(admin, payload.profile_id)
  requireProfile(profile)
  const inputs = Array.isArray(payload.samples)
    ? payload.samples
    : [
        {
          title: payload.title || "",
          raw_text: payload.raw_text || "",
          source_type: payload.source_type || "uploaded",
        },
      ]
  return insertWritingSamples(profile.id, inputs, payload.source_type || "uploaded")
}

export async function importLinkedInPostsServer(payload: {
  profile_id?: string
  posts?: Array<{ title?: string; text?: string; url?: string; language?: string }>
}) {
  await requireResearchUser()
  const admin = createResearchAdminClient()
  const profile = await resolveProfile(admin, payload.profile_id)
  requireProfile(profile)
  const posts = Array.isArray(payload.posts) ? payload.posts : []
  if (!posts.length) throw new Error("LinkedIn import requires a `posts` array.")
  return insertWritingSamples(
    profile.id,
    posts.map((post, index) => ({
      title: String(post.title || `LinkedIn Post ${index + 1}`),
      raw_text: String(post.text || ""),
      raw_blob_url: String(post.url || ""),
      source_type: "linkedin",
      language: String(post.language || "en"),
    })),
    "linkedin",
  )
}

export async function handleIdeaActionServer(
  ideaId: string,
  action: UserFeedbackEventType,
  payload: { profile_id?: string; note?: string },
) {
  await requireResearchUser()
  const admin = createResearchAdminClient()
  const profile = await resolveProfile(admin, payload.profile_id)
  requireProfile(profile)
  const feedbackRow = {
    id: `feedback_${randomUUID().replace(/-/g, "").slice(0, 12)}`,
    research_profile_id: profile.id,
    idea_card_id: ideaId,
    event_type: action,
    event_payload: payload.note ? { note: String(payload.note).trim() } : {},
    created_at: nowIso(),
  }
  const { error: feedbackError } = await admin.from("user_feedback_events").insert(feedbackRow)
  if (feedbackError) throw new Error(feedbackError.message)
  if (action === "save" || action === "discard") {
    const status = action === "save" ? "saved" : "discarded"
    const { error: updateError } = await admin.from("idea_cards").update({ status }).eq("id", ideaId)
    if (updateError) throw new Error(updateError.message)
    return { ok: true, idea_id: ideaId, event: action, status }
  }
  return { ok: true, idea_id: ideaId, event: action, status: null }
}

function plusMs(date: Date, ms: number): Date {
  return new Date(date.getTime() + ms)
}

function nextDailyUtc(hour: number, now: Date): Date {
  const target = new Date(now)
  target.setUTCHours(hour, 0, 0, 0)
  if (target <= now) target.setUTCDate(target.getUTCDate() + 1)
  return target
}

function nextWeeklyUtc(weekday: number, hour: number, now: Date): Date {
  const target = new Date(now)
  target.setUTCHours(hour, 0, 0, 0)
  const daysAhead = (weekday - target.getUTCDay() + 7) % 7
  target.setUTCDate(target.getUTCDate() + daysAhead)
  if (target <= now) target.setUTCDate(target.getUTCDate() + 7)
  return target
}

function seedScheduleFor(jobType: JobType, now: Date): Date {
  if (jobType === "collect_sources") return now
  if (jobType === "discover_creators") return plusMs(now, 60 * 1000)
  if (
    jobType === "refresh_style_profile" ||
    jobType === "cluster_items" ||
    jobType === "rank_topics" ||
    jobType === "generate_ideas"
  ) {
    return nextDailyUtc(DEFAULT_DAILY_HOUR_UTC, now)
  }
  return nextWeeklyUtc(DEFAULT_WEEKLY_WEEKDAY_UTC, DEFAULT_WEEKLY_HOUR_UTC, now)
}

function recurringNextSchedule(jobType: JobType, reference: Date): Date {
  if (jobType === "collect_sources" || jobType === "discover_creators") {
    return plusMs(reference, COLLECTION_INTERVAL_MS)
  }
  if (
    jobType === "refresh_style_profile" ||
    jobType === "cluster_items" ||
    jobType === "rank_topics" ||
    jobType === "generate_ideas"
  ) {
    return nextDailyUtc(DEFAULT_DAILY_HOUR_UTC, reference)
  }
  return nextWeeklyUtc(DEFAULT_WEEKLY_WEEKDAY_UTC, DEFAULT_WEEKLY_HOUR_UTC, reference)
}

async function ensureRecurringJobs(admin: ResearchAdminClient, profileId: string) {
  const { data, error } = await admin
    .from("job_runs")
    .select("id, job_type, status, scheduled_for, finished_at")
    .eq("research_profile_id", profileId)
    .order("scheduled_for", { ascending: false })
    .limit(200)
  if (error) throw new Error(error.message)
  const jobs = (data || []) as Array<{
    id: string
    job_type: JobType
    status: JobStatus
    scheduled_for: string
    finished_at: string | null
  }>
  const now = new Date()
  const inserts = RESEARCH_JOB_TYPES.flatMap((jobType) => {
    const open = jobs.find((job) => job.job_type === jobType && (job.status === "pending" || job.status === "running"))
    if (open) return []
    const latest = jobs.find((job) => job.job_type === jobType)
    const scheduledFor = latest
      ? recurringNextSchedule(jobType, new Date(latest.finished_at || latest.scheduled_for))
      : seedScheduleFor(jobType, now)
    return [
      {
        id: `job_${randomUUID().replace(/-/g, "").slice(0, 12)}`,
        research_profile_id: profileId,
        job_type: jobType,
        status: "pending",
        scheduled_for: scheduledFor.toISOString(),
        started_at: null,
        finished_at: null,
        attempt_count: 0,
        input_snapshot: {},
        error_summary: "",
        next_run_at: null,
        heartbeat_at: null,
        lease_token: "",
        lease_owner: "",
        lease_expires_at: null,
        dispatched_at: null,
      },
    ]
  })
  if (!inserts.length) return 0
  const { error: insertError } = await admin.from("job_runs").insert(inserts)
  if (insertError) throw new Error(insertError.message)
  return inserts.length
}

async function dispatchWorkflow(job: JobRunRow, trigger: string) {
  const request = buildGitHubDispatchRequest(job, trigger)
  const response = await fetch(request.url, {
    method: "POST",
    headers: request.headers,
    body: JSON.stringify(request.body),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`GitHub workflow dispatch failed with ${response.status}: ${text}`)
  }
}

async function verifyDatabaseServer(): Promise<NonNullable<VerificationPayload["database"]>> {
  const missingFields: string[] = []
  const url = supabaseUrl()
  const serviceRoleKey = supabaseServiceRoleKey()
  const dbDsn = String(process.env.AGENT_REACH_RESEARCH_DB_DSN || "").trim()
  if (!url) missingFields.push("NEXT_PUBLIC_SUPABASE_URL")
  if (!serviceRoleKey) {
    missingFields.push("AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY")
  }
  if (!dbDsn) missingFields.push("AGENT_REACH_RESEARCH_DB_DSN")

  const target = url || "supabase://unconfigured"
  if (!url || !serviceRoleKey) {
    return {
      backend: "supabase",
      status: "degraded",
      target,
      missing_fields: missingFields,
      remediation_hint: "Set the Supabase URL, service role key, and Postgres DSN for app routes plus Python runners.",
    }
  }

  const admin = createResearchAdminClient()
  const { count, error } = await admin.from("research_profiles").select("id", { head: true, count: "exact" })
  return {
    backend: "supabase",
    status: error || missingFields.length ? "degraded" : "ok",
    target,
    result: count ?? 0,
    error: error?.message,
    missing_fields: missingFields.length ? missingFields : undefined,
    remediation_hint: missingFields.length
      ? "The dashboard can reach Supabase, but Python runners still need the Postgres DSN."
      : null,
  }
}

async function verifyBlobStoreServer(): Promise<NonNullable<VerificationPayload["blob_store"]>> {
  const missingFields: string[] = []
  const bucket = String(process.env.AGENT_REACH_RESEARCH_BLOB_BUCKET || "").trim()
  const prefix = String(process.env.AGENT_REACH_RESEARCH_BLOB_PREFIX || "agent-reach/research").trim()
  const url = supabaseUrl()
  const serviceRoleKey = supabaseServiceRoleKey()
  if (!bucket) missingFields.push("AGENT_REACH_RESEARCH_BLOB_BUCKET")
  if (!url) missingFields.push("NEXT_PUBLIC_SUPABASE_URL")
  if (!serviceRoleKey) {
    missingFields.push("AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY")
  }

  const probeUri = bucket ? `supabase://${bucket}/${prefix}` : "supabase://unconfigured"
  if (!bucket || !url || !serviceRoleKey) {
    return {
      backend: "supabase",
      status: "degraded",
      target: bucket || "unconfigured",
      probe_uri: probeUri,
      missing_fields: missingFields,
      remediation_hint: "Set the Supabase Storage bucket plus service-role-backed server credentials.",
    }
  }

  const admin = createResearchAdminClient()
  const { error } = await admin.storage.from(bucket).list(prefix, { limit: 1 })
  return {
    backend: "supabase",
    status: error ? "degraded" : "ok",
    target: bucket,
    probe_uri: probeUri,
    error: error?.message,
    remediation_hint: error ? "Ensure the Storage bucket exists and the service role key can access it." : null,
  }
}

function verificationCheck(
  source: string,
  available: boolean,
  hint: string,
  error?: string,
): VerificationSourceCheckPayload {
  return {
    source,
    available,
    hint,
    status: available ? "ok" : "degraded",
    ...(error ? { error } : {}),
  }
}

function verifyExternalRunnerChecks(): NonNullable<VerificationPayload["sources"]> {
  const checks: VerificationSourceCheckPayload[] = []
  checks.push(
    verificationCheck(
      "qstash-scheduler",
      qstashConfigured(),
      qstashConfigured()
        ? "Upstash QStash signing keys are present. Point the schedule at /api/internal/scheduler every 5 minutes."
        : "Missing QSTASH_CURRENT_SIGNING_KEY/QSTASH_NEXT_SIGNING_KEY for signed scheduler delivery.",
    ),
  )
  checks.push(
    verificationCheck(
      "github-actions",
      githubDispatchConfigured(),
      githubDispatchConfigured()
        ? "GitHub workflow dispatch is configured for claimed job execution."
        : gitHubDispatchErrorMessage(),
    ),
  )
  const encryptionConfigured = Boolean(String(process.env.RESEARCH_SETTINGS_ENCRYPTION_KEY || "").trim())
  checks.push(
    verificationCheck(
      "python-runner-config",
      encryptionConfigured,
      encryptionConfigured
        ? "Encrypted provider settings can be decrypted server-side by app routes and Python runners."
        : "Missing RESEARCH_SETTINGS_ENCRYPTION_KEY for encrypted OpenAI settings.",
    ),
  )
  checks.push(
    verificationCheck(
      "source-smoke-checks",
      githubDispatchConfigured(),
      "Live source collection checks run through the Python runtime with `agent-reach research verify sources --run-collect`.",
    ),
  )
  return {
    generated_at: nowIso(),
    status: checks.every((check) => check.status === "ok") ? "ok" : "degraded",
    run_collect: false,
    checks,
  }
}

export async function runSystemVerificationServer(payload: {
  mode?: string
  profile_id?: string | null
}): Promise<VerificationPayload> {
  await requireResearchUser()
  const mode = String(payload.mode || "all")
  const generatedAt = nowIso()
  const verification: VerificationPayload = {
    generated_at: generatedAt,
    profile_id: payload.profile_id || null,
    status: "ok",
  }

  if (mode === "storage" || mode === "all") {
    const [database, blob_store] = await Promise.all([verifyDatabaseServer(), verifyBlobStoreServer()])
    verification.database = database
    verification.blob_store = blob_store
    verification.storage = {
      generated_at: generatedAt,
      database,
      blob_store,
    }
  }

  if (mode === "sources" || mode === "all") {
    verification.sources = verifyExternalRunnerChecks()
  }

  const statuses = [
    verification.storage?.database?.status,
    verification.storage?.blob_store?.status,
    verification.sources?.status,
  ].filter(Boolean)
  verification.status = statuses.every((status) => status === "ok") ? "ok" : "degraded"
  return verification
}

export async function queueManualRunServer(payload: { profile_id?: string; job: string }) {
  await requireResearchUser()
  if (!githubDispatchConfigured()) {
    throw new Error(gitHubDispatchErrorMessage())
  }
  const admin = createResearchAdminClient()
  const profile = await resolveProfile(admin, payload.profile_id)
  requireProfile(profile)
  const now = nowIso()
  const requestedTypes =
    payload.job === "all"
      ? [
          "collect_sources",
          "discover_creators",
          "refresh_style_profile",
          "cluster_items",
          "rank_topics",
          "generate_ideas",
        ]
      : [payload.job]
  const validJobTypes = requestedTypes.filter((job): job is JobType =>
    RESEARCH_JOB_TYPES.includes(job as JobType),
  )
  if (!validJobTypes.length) {
    throw new Error("Unknown manual job.")
  }
  const openJobsResult = await admin
    .from("job_runs")
    .select("job_type, status")
    .eq("research_profile_id", profile.id)
    .in("status", ["pending", "running"])
  if (openJobsResult.error) throw new Error(openJobsResult.error.message)
  const openJobTypes = new Set((openJobsResult.data || []).map((job) => job.job_type as JobType))
  const inserts = validJobTypes
    .filter((job) => !openJobTypes.has(job))
    .map((jobType) => ({
      id: `job_${randomUUID().replace(/-/g, "").slice(0, 12)}`,
      research_profile_id: profile.id,
      job_type: jobType,
      status: "pending",
      scheduled_for: now,
      started_at: null,
      finished_at: null,
      attempt_count: 0,
      input_snapshot: { trigger: "manual" },
      error_summary: "",
      next_run_at: null,
      heartbeat_at: null,
      lease_token: "",
      lease_owner: "",
      lease_expires_at: null,
      dispatched_at: null,
    }))
  if (inserts.length) {
    const { error } = await admin.from("job_runs").insert(inserts)
    if (error) throw new Error(error.message)
  }
  const dispatch = await dispatchDueJobsServer({ leaseOwner: "manual-run", trigger: "manual" })
  return {
    ok: true,
    queued: inserts.length,
    dispatch,
  }
}

export async function dispatchDueJobsServer(options?: {
  limit?: number
  leaseOwner?: string
  trigger?: string
}) {
  if (!githubDispatchConfigured()) {
    throw new Error(gitHubDispatchErrorMessage())
  }
  const admin = createResearchAdminClient()
  const profile = await fetchLatestProfile(admin)
  if (!profile) {
    return { claimed: 0, dispatched: 0, released: 0, seeded: 0, jobs: [] as string[] }
  }
  const seeded = await ensureRecurringJobs(admin, profile.id)
  const { data, error } = await admin.rpc("claim_due_job_runs", {
    p_now: nowIso(),
    p_limit: options?.limit || 4,
    p_lease_seconds: 20 * 60,
    p_lease_owner: options?.leaseOwner || "scheduler",
  })
  if (error) throw new Error(error.message)
  const jobs = ((data || []) as JobRunRow[]).map((job) => job)
  let dispatched = 0
  let released = 0
  for (const job of jobs) {
    try {
      await dispatchWorkflow(job, options?.trigger || "scheduler")
      dispatched += 1
      const { error: dispatchError } = await admin
        .from("job_runs")
        .update({ dispatched_at: nowIso() })
        .eq("id", job.id)
      if (dispatchError) throw new Error(dispatchError.message)
    } catch {
      released += 1
      const { error: releaseError } = await admin
        .from("job_runs")
        .update({
          status: "pending",
          lease_token: "",
          lease_owner: "",
          lease_expires_at: null,
          dispatched_at: null,
          scheduled_for: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
        })
        .eq("id", job.id)
      if (releaseError) throw new Error(releaseError.message)
    }
  }
  return { claimed: jobs.length, dispatched, released, seeded, jobs: jobs.map((job) => job.id) }
}
