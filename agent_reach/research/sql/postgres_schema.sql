-- Content Research Studio v1 Postgres schema
-- Source of truth alignment:
-- - relational tables for all required entities
-- - pgvector extension for future similarity search
-- - JSONB for flexible engagement, payload, and marker fields

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS research_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    persona_brief TEXT NOT NULL,
    niche_definition TEXT NOT NULL,
    must_track_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    excluded_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_audience TEXT NOT NULL DEFAULT '',
    desired_formats JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS writing_samples (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    raw_blob_url TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS style_profiles (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    tone_markers JSONB NOT NULL DEFAULT '[]'::jsonb,
    hook_patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
    structure_patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferred_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    avoided_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding_version TEXT NOT NULL,
    raw_summary TEXT NOT NULL DEFAULT '',
    generated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS creator_watchlists (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    creator_external_id TEXT NOT NULL,
    creator_name TEXT NOT NULL,
    creator_url TEXT NOT NULL,
    watch_reason TEXT NOT NULL,
    watch_score DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (research_profile_id, source, creator_external_id)
);

CREATE TABLE IF NOT EXISTS source_items (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    author_name TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    title TEXT NOT NULL,
    body_text TEXT NOT NULL,
    engagement_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_blob_url TEXT NOT NULL DEFAULT '',
    health_status TEXT NOT NULL DEFAULT 'ok',
    source_query TEXT NOT NULL DEFAULT '',
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (research_profile_id, source, external_id)
);

CREATE TABLE IF NOT EXISTS topic_clusters (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    cluster_label TEXT NOT NULL,
    cluster_summary TEXT NOT NULL,
    representative_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    supporting_item_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_family_count INTEGER NOT NULL DEFAULT 0,
    freshness_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    cluster_key TEXT NOT NULL,
    final_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    score_components JSONB NOT NULL DEFAULT '{}'::jsonb,
    rank_snapshot_at TIMESTAMPTZ NOT NULL,
    UNIQUE (research_profile_id, cluster_key)
);

CREATE TABLE IF NOT EXISTS idea_cards (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    topic_cluster_id TEXT NOT NULL REFERENCES topic_clusters(id) ON DELETE CASCADE,
    headline TEXT NOT NULL,
    hook TEXT NOT NULL,
    why_now TEXT NOT NULL,
    outline_md TEXT NOT NULL,
    evidence_item_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    final_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    generated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (research_profile_id, topic_cluster_id)
);

CREATE TABLE IF NOT EXISTS weekly_reports (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    report_period_start TIMESTAMPTZ NOT NULL,
    report_period_end TIMESTAMPTZ NOT NULL,
    top_idea_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_creator_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary_md TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    UNIQUE (research_profile_id, report_period_start, report_period_end)
);

CREATE TABLE IF NOT EXISTS user_feedback_events (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    idea_card_id TEXT NOT NULL REFERENCES idea_cards(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_requests (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    trigger TEXT NOT NULL,
    status TEXT NOT NULL,
    query_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    latest_stage TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    source_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS job_runs (
    id TEXT PRIMARY KEY,
    research_profile_id TEXT NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    refresh_request_id TEXT NOT NULL DEFAULT '',
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL,
    depends_on_job_run_id TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    current_step TEXT NOT NULL DEFAULT '',
    current_source TEXT NOT NULL DEFAULT '',
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT NOT NULL DEFAULT '',
    next_run_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    lease_token TEXT NOT NULL DEFAULT '',
    lease_owner TEXT NOT NULL DEFAULT '',
    lease_expires_at TIMESTAMPTZ,
    dispatched_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS job_run_events (
    id TEXT PRIMARY KEY,
    job_run_id TEXT NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    refresh_request_id TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    step TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 0,
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS refresh_request_id TEXT NOT NULL DEFAULT '';
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS depends_on_job_run_id TEXT NOT NULL DEFAULT '';
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS output_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS current_step TEXT NOT NULL DEFAULT '';
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS current_source TEXT NOT NULL DEFAULT '';
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS progress_current INTEGER NOT NULL DEFAULT 0;
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS progress_total INTEGER NOT NULL DEFAULT 0;
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS lease_token TEXT NOT NULL DEFAULT '';
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS lease_owner TEXT NOT NULL DEFAULT '';
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS dispatched_at TIMESTAMPTZ;

CREATE OR REPLACE FUNCTION claim_due_job_runs(
    p_now TIMESTAMPTZ,
    p_limit INTEGER DEFAULT 1,
    p_lease_seconds INTEGER DEFAULT 900,
    p_lease_owner TEXT DEFAULT 'scheduler'
)
RETURNS SETOF job_runs
LANGUAGE plpgsql
AS $$
DECLARE
    v_ids TEXT[];
BEGIN
    WITH candidates AS (
        SELECT id
        FROM job_runs
        WHERE (
            status = 'pending' AND scheduled_for <= p_now
            AND (
                depends_on_job_run_id = ''
                OR EXISTS (
                    SELECT 1
                    FROM job_runs dep
                    WHERE dep.id = job_runs.depends_on_job_run_id
                      AND dep.status = 'succeeded'
                )
            )
        ) OR (
            status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= p_now
        )
        ORDER BY scheduled_for ASC
        FOR UPDATE SKIP LOCKED
        LIMIT GREATEST(p_limit, 1)
    ),
    updated AS (
        UPDATE job_runs j
        SET status = 'running',
            started_at = COALESCE(j.started_at, p_now),
            finished_at = NULL,
            attempt_count = j.attempt_count + 1,
            heartbeat_at = p_now,
            error_summary = '',
            lease_token = md5(random()::text || clock_timestamp()::text || j.id),
            lease_owner = COALESCE(NULLIF(p_lease_owner, ''), 'scheduler'),
            lease_expires_at = p_now + make_interval(secs => GREATEST(p_lease_seconds, 60)),
            dispatched_at = NULL
        FROM candidates c
        WHERE j.id = c.id
        RETURNING j.id
    )
    SELECT array_agg(id) INTO v_ids FROM updated;

    IF v_ids IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT *
    FROM job_runs
    WHERE id = ANY(v_ids)
    ORDER BY scheduled_for ASC;
END;
$$;

CREATE TABLE IF NOT EXISTS research_user_settings (
    user_id TEXT PRIMARY KEY,
    openai_api_key_ciphertext TEXT,
    openai_api_key_last4 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_runs_due
    ON job_runs (status, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_job_runs_lease
    ON job_runs (status, lease_expires_at);

CREATE INDEX IF NOT EXISTS idx_refresh_requests_profile_created
    ON refresh_requests (research_profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_runs_refresh
    ON job_runs (refresh_request_id, scheduled_for ASC);

CREATE INDEX IF NOT EXISTS idx_job_run_events_refresh_created
    ON job_run_events (refresh_request_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_source_items_profile_published
    ON source_items (research_profile_id, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_clusters_profile_score
    ON topic_clusters (research_profile_id, final_score DESC, freshness_score DESC);

CREATE INDEX IF NOT EXISTS idx_idea_cards_profile_score
    ON idea_cards (research_profile_id, final_score DESC, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_profile_created
    ON user_feedback_events (research_profile_id, created_at ASC);

-- Suggested pgvector indexes for later production migration:
-- CREATE INDEX idx_writing_samples_embedding ON writing_samples USING ivfflat (embedding vector_cosine_ops);
-- CREATE INDEX idx_source_items_embedding ON source_items USING ivfflat (embedding vector_cosine_ops);
