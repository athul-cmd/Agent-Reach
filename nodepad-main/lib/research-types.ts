export interface ResearchProfilePayload {
  id: string
  name: string
  persona_brief: string
  niche_definition: string
  must_track_topics: string[]
  excluded_topics: string[]
  target_audience: string
  desired_formats: string[]
  status: string
  created_at: string
  updated_at: string
}

export interface StyleProfilePayload {
  id: string
  research_profile_id: string
  tone_markers: string[]
  hook_patterns: string[]
  structure_patterns: string[]
  preferred_topics: string[]
  avoided_topics: string[]
  evidence_preferences: string[]
  embedding_version: string
  raw_summary: string
  generated_at: string
}

export interface SourceItemPayload {
  id: string
  research_profile_id: string
  source: string
  external_id: string
  canonical_url: string
  author_name: string
  published_at: string
  title: string
  body_text: string
  engagement: Record<string, unknown>
  raw_blob_url: string
  health_status: string
  source_query: string
  created_at: string
}

export interface TopicClusterPayload {
  id: string
  research_profile_id: string
  cluster_label: string
  cluster_summary: string
  representative_terms: string[]
  supporting_item_ids: string[]
  source_family_count: number
  freshness_score: number
  cluster_key: string
  final_score: number
  score_components: Record<string, number>
  rank_snapshot_at: string
}

export interface IdeaCardPayload {
  id: string
  research_profile_id: string
  topic_cluster_id: string
  headline: string
  hook: string
  why_now: string
  outline_md: string
  evidence_item_ids: string[]
  final_score: number
  status: string
  generated_at: string
}

export interface CreatorWatchPayload {
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

export interface WeeklyReportPayload {
  id: string
  research_profile_id: string
  report_period_start: string
  report_period_end: string
  top_idea_ids: string[]
  top_creator_ids: string[]
  summary_md: string
  published_at: string
}

export interface JobRunPayload {
  id: string
  research_profile_id: string
  job_type: string
  status: string
  scheduled_for: string
  started_at: string | null
  finished_at: string | null
  attempt_count: number
  input_snapshot: Record<string, unknown>
  error_summary: string
  next_run_at: string | null
  heartbeat_at: string | null
}

export interface SourceHealthPayload {
  source: string
  status: string
  available: boolean
  hint: string
  item_count: number
  latest_published_at: string | null
  latest_health_status: string | null
  stale: boolean
}

export interface VerificationSourceCheckPayload {
  source: string
  available: boolean
  hint: string
  status: string
  sample_count?: number
  error?: string
}

export interface WorkerHealthPayload {
  status: string
  state: string
  note: string
  stale: boolean
  last_update_at: string | null
  tick_count: number
  active_profile_id: string | null
  last_result: Record<string, unknown> | null
  last_error: string | null
}

export interface JobHealthPayload {
  status: string
  latest_jobs: {
    job_type: string
    status: string
    scheduled_for: string
    finished_at: string | null
    error_summary: string
  }[]
  failed_job_count: number
  pending_job_count: number
}

export interface SystemHealthPayload {
  generated_at: string
  status: string
  worker: WorkerHealthPayload
  jobs: JobHealthPayload
  sources: SourceHealthPayload[]
  storage: Record<string, string>
}

export interface VerificationPayload {
  generated_at: string
  status: string
  profile_id?: string | null
  storage?: {
    generated_at?: string
    database?: {
      backend: string
      status: string
      target: string
      result?: number | null
      error?: string
      missing_fields?: string[]
      remediation_hint?: string | null
    }
    blob_store?: {
      backend: string
      status: string
      target: string
      probe_uri?: string
      deleted_count?: number
      error?: string
      missing_fields?: string[]
      remediation_hint?: string | null
    }
  }
  sources?: {
    generated_at?: string
    status: string
    run_collect: boolean
    checks: VerificationSourceCheckPayload[]
  }
  database?: {
    backend: string
    status: string
    target: string
    result?: number | null
    error?: string
    missing_fields?: string[]
    remediation_hint?: string | null
  }
  blob_store?: {
    backend: string
    status: string
    target: string
    probe_uri?: string
    deleted_count?: number
    error?: string
    missing_fields?: string[]
    remediation_hint?: string | null
  }
}

export interface ResearchDashboardData {
  available: boolean
  apiBaseUrl: string
  error: string | null
  generated_at: string | null
  system_health: SystemHealthPayload | null
  profile: ResearchProfilePayload | null
  style_profile: StyleProfilePayload | null
  report: WeeklyReportPayload | null
  source_items: SourceItemPayload[]
  clusters: TopicClusterPayload[]
  ideas: IdeaCardPayload[]
  creators: CreatorWatchPayload[]
  jobs: JobRunPayload[]
  metrics: {
    source_item_count: number
    cluster_count: number
    idea_count: number
    creator_count: number
  }
}

export interface OpenAISettingsPayload {
  configured: boolean
  masked_value: string
  last4: string
  updated_at: string | null
}

export interface ResearchProfileInput {
  name: string
  persona_brief: string
  niche_definition: string
  target_audience?: string
  must_track_topics?: string[]
  excluded_topics?: string[]
  desired_formats?: string[]
}
