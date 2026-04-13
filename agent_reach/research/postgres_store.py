# -*- coding: utf-8 -*-
"""Postgres-backed research store."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, List, Optional
from uuid import uuid4

from agent_reach.research.models import (
    CreatorWatch,
    IdeaCard,
    JobRun,
    JobStatus,
    JobType,
    ResearchProfile,
    SourceItem,
    StyleProfile,
    TopicCluster,
    UserFeedbackEvent,
    WeeklyReport,
    WritingSample,
)
from agent_reach.research.store_utils import dump_json as _dump
from agent_reach.research.store_utils import iso_datetime as _iso
from agent_reach.research.store_utils import load_json as _load
from agent_reach.research.store_utils import parse_datetime as _dt


class PostgresResearchStore:
    """Durable Postgres store for production-oriented research data."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "Postgres backend requires `psycopg`. Install with `pip install 'agent-reach[postgres]'`."
            ) from exc
        return psycopg.connect(self.dsn, row_factory=dict_row)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        schema_path = Path(__file__).parent / "sql" / "postgres_schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    def upsert_profile(self, profile: ResearchProfile) -> ResearchProfile:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO research_profiles (
                        id, name, persona_brief, niche_definition, must_track_topics,
                        excluded_topics, target_audience, desired_formats, status,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        persona_brief = EXCLUDED.persona_brief,
                        niche_definition = EXCLUDED.niche_definition,
                        must_track_topics = EXCLUDED.must_track_topics,
                        excluded_topics = EXCLUDED.excluded_topics,
                        target_audience = EXCLUDED.target_audience,
                        desired_formats = EXCLUDED.desired_formats,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        profile.id,
                        profile.name,
                        profile.persona_brief,
                        profile.niche_definition,
                        _dump(profile.must_track_topics),
                        _dump(profile.excluded_topics),
                        profile.target_audience,
                        _dump(profile.desired_formats),
                        profile.status,
                        _iso(profile.created_at),
                        _iso(profile.updated_at),
                    ),
                )
        return profile

    def get_profile(self, profile_id: str) -> Optional[ResearchProfile]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM research_profiles WHERE id = %s", (profile_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def get_latest_profile(self) -> Optional[ResearchProfile]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM research_profiles ORDER BY updated_at DESC LIMIT 1")
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def add_writing_sample(self, sample: WritingSample) -> WritingSample:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO writing_samples (
                        id, research_profile_id, source_type, title, raw_text,
                        raw_blob_url, language, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        source_type = EXCLUDED.source_type,
                        title = EXCLUDED.title,
                        raw_text = EXCLUDED.raw_text,
                        raw_blob_url = EXCLUDED.raw_blob_url,
                        language = EXCLUDED.language
                    """,
                    (
                        sample.id,
                        sample.research_profile_id,
                        sample.source_type,
                        sample.title,
                        sample.raw_text,
                        sample.raw_blob_url,
                        sample.language,
                        _iso(sample.created_at),
                    ),
                )
        return sample

    def list_writing_samples(self, research_profile_id: str) -> List[WritingSample]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM writing_samples
                    WHERE research_profile_id = %s
                    ORDER BY created_at ASC
                    """,
                    (research_profile_id,),
                )
                rows = cur.fetchall()
        return [
            WritingSample(
                id=row["id"],
                research_profile_id=row["research_profile_id"],
                source_type=row["source_type"],
                title=row["title"],
                raw_text=row["raw_text"],
                raw_blob_url=row["raw_blob_url"],
                language=row["language"],
                created_at=_dt(row["created_at"]) or datetime.now(timezone.utc),
            )
            for row in rows
        ]

    def upsert_style_profile(self, style_profile: StyleProfile) -> StyleProfile:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO style_profiles (
                        id, research_profile_id, tone_markers, hook_patterns,
                        structure_patterns, preferred_topics, avoided_topics,
                        evidence_preferences, embedding_version, raw_summary, generated_at
                    ) VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        tone_markers = EXCLUDED.tone_markers,
                        hook_patterns = EXCLUDED.hook_patterns,
                        structure_patterns = EXCLUDED.structure_patterns,
                        preferred_topics = EXCLUDED.preferred_topics,
                        avoided_topics = EXCLUDED.avoided_topics,
                        evidence_preferences = EXCLUDED.evidence_preferences,
                        embedding_version = EXCLUDED.embedding_version,
                        raw_summary = EXCLUDED.raw_summary,
                        generated_at = EXCLUDED.generated_at
                    """,
                    (
                        style_profile.id,
                        style_profile.research_profile_id,
                        _dump(style_profile.tone_markers),
                        _dump(style_profile.hook_patterns),
                        _dump(style_profile.structure_patterns),
                        _dump(style_profile.preferred_topics),
                        _dump(style_profile.avoided_topics),
                        _dump(style_profile.evidence_preferences),
                        style_profile.embedding_version,
                        style_profile.raw_summary,
                        _iso(style_profile.generated_at),
                    ),
                )
        return style_profile

    def get_latest_style_profile(self, research_profile_id: str) -> Optional[StyleProfile]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM style_profiles
                    WHERE research_profile_id = %s
                    ORDER BY generated_at DESC
                    LIMIT 1
                    """,
                    (research_profile_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return StyleProfile(
            id=row["id"],
            research_profile_id=row["research_profile_id"],
            tone_markers=_load(row["tone_markers"], []),
            hook_patterns=_load(row["hook_patterns"], []),
            structure_patterns=_load(row["structure_patterns"], []),
            preferred_topics=_load(row["preferred_topics"], []),
            avoided_topics=_load(row["avoided_topics"], []),
            evidence_preferences=_load(row["evidence_preferences"], []),
            embedding_version=row["embedding_version"],
            raw_summary=row["raw_summary"],
            generated_at=_dt(row["generated_at"]) or datetime.now(timezone.utc),
        )

    def upsert_source_items(self, items: List[SourceItem]) -> None:
        if not items:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO source_items (
                        id, research_profile_id, source, external_id, canonical_url,
                        author_name, published_at, title, body_text, engagement_json,
                        raw_blob_url, health_status, source_query, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                    ON CONFLICT (research_profile_id, source, external_id) DO UPDATE SET
                        canonical_url = EXCLUDED.canonical_url,
                        author_name = EXCLUDED.author_name,
                        published_at = EXCLUDED.published_at,
                        title = EXCLUDED.title,
                        body_text = EXCLUDED.body_text,
                        engagement_json = EXCLUDED.engagement_json,
                        raw_blob_url = EXCLUDED.raw_blob_url,
                        health_status = EXCLUDED.health_status,
                        source_query = EXCLUDED.source_query
                    """,
                    [
                        (
                            item.id,
                            item.research_profile_id,
                            item.source,
                            item.external_id,
                            item.canonical_url,
                            item.author_name,
                            _iso(item.published_at),
                            item.title,
                            item.body_text,
                            _dump(item.engagement),
                            item.raw_blob_url,
                            item.health_status,
                            item.source_query,
                            _iso(item.created_at),
                        )
                        for item in items
                    ],
                )

    def list_source_items(self, research_profile_id: str, limit: Optional[int] = None) -> List[SourceItem]:
        query = """
            SELECT * FROM source_items
            WHERE research_profile_id = %s
            ORDER BY published_at DESC
        """
        params: list[Any] = [research_profile_id]
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [
            SourceItem(
                id=row["id"],
                research_profile_id=row["research_profile_id"],
                source=row["source"],
                external_id=row["external_id"],
                canonical_url=row["canonical_url"],
                author_name=row["author_name"],
                published_at=_dt(row["published_at"]) or datetime.now(timezone.utc),
                title=row["title"],
                body_text=row["body_text"],
                engagement=_load(row["engagement_json"], {}),
                raw_blob_url=row["raw_blob_url"],
                health_status=row["health_status"],
                source_query=row.get("source_query", ""),
                created_at=_dt(row["created_at"]) or datetime.now(timezone.utc),
            )
            for row in rows
        ]

    def upsert_clusters(self, clusters: List[TopicCluster]) -> None:
        if not clusters:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO topic_clusters (
                        id, research_profile_id, cluster_label, cluster_summary,
                        representative_terms, supporting_item_ids, source_family_count,
                        freshness_score, cluster_key, final_score, score_components,
                        rank_snapshot_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (research_profile_id, cluster_key) DO UPDATE SET
                        cluster_label = EXCLUDED.cluster_label,
                        cluster_summary = EXCLUDED.cluster_summary,
                        representative_terms = EXCLUDED.representative_terms,
                        supporting_item_ids = EXCLUDED.supporting_item_ids,
                        source_family_count = EXCLUDED.source_family_count,
                        freshness_score = EXCLUDED.freshness_score,
                        final_score = EXCLUDED.final_score,
                        score_components = EXCLUDED.score_components,
                        rank_snapshot_at = EXCLUDED.rank_snapshot_at
                    """,
                    [
                        (
                            cluster.id,
                            cluster.research_profile_id,
                            cluster.cluster_label,
                            cluster.cluster_summary,
                            _dump(cluster.representative_terms),
                            _dump(cluster.supporting_item_ids),
                            cluster.source_family_count,
                            cluster.freshness_score,
                            cluster.cluster_key,
                            cluster.final_score,
                            _dump(cluster.score_components),
                            _iso(cluster.rank_snapshot_at),
                        )
                        for cluster in clusters
                    ],
                )

    def list_clusters(self, research_profile_id: str) -> List[TopicCluster]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM topic_clusters
                    WHERE research_profile_id = %s
                    ORDER BY final_score DESC, freshness_score DESC, cluster_label ASC
                    """,
                    (research_profile_id,),
                )
                rows = cur.fetchall()
        return [
            TopicCluster(
                id=row["id"],
                research_profile_id=row["research_profile_id"],
                cluster_label=row["cluster_label"],
                cluster_summary=row["cluster_summary"],
                representative_terms=_load(row["representative_terms"], []),
                supporting_item_ids=_load(row["supporting_item_ids"], []),
                source_family_count=row["source_family_count"],
                freshness_score=row["freshness_score"],
                cluster_key=row["cluster_key"],
                final_score=row["final_score"],
                score_components=_load(row["score_components"], {}),
                rank_snapshot_at=_dt(row["rank_snapshot_at"]) or datetime.now(timezone.utc),
            )
            for row in rows
        ]

    def upsert_idea_cards(self, ideas: List[IdeaCard]) -> None:
        if not ideas:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO idea_cards (
                        id, research_profile_id, topic_cluster_id, headline, hook, why_now,
                        outline_md, evidence_item_ids, final_score, status, generated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (research_profile_id, topic_cluster_id) DO UPDATE SET
                        headline = EXCLUDED.headline,
                        hook = EXCLUDED.hook,
                        why_now = EXCLUDED.why_now,
                        outline_md = EXCLUDED.outline_md,
                        evidence_item_ids = EXCLUDED.evidence_item_ids,
                        final_score = EXCLUDED.final_score,
                        status = EXCLUDED.status,
                        generated_at = EXCLUDED.generated_at
                    """,
                    [
                        (
                            idea.id,
                            idea.research_profile_id,
                            idea.topic_cluster_id,
                            idea.headline,
                            idea.hook,
                            idea.why_now,
                            idea.outline_md,
                            _dump(idea.evidence_item_ids),
                            idea.final_score,
                            idea.status,
                            _iso(idea.generated_at),
                        )
                        for idea in ideas
                    ],
                )

    def list_idea_cards(
        self,
        research_profile_id: str,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[IdeaCard]:
        query = """
            SELECT * FROM idea_cards
            WHERE research_profile_id = %s
        """
        params: list[Any] = [research_profile_id]
        if status is not None:
            query += " AND status = %s"
            params.append(status)
        query += " ORDER BY final_score DESC, generated_at DESC"
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [
            IdeaCard(
                id=row["id"],
                research_profile_id=row["research_profile_id"],
                topic_cluster_id=row["topic_cluster_id"],
                headline=row["headline"],
                hook=row["hook"],
                why_now=row["why_now"],
                outline_md=row["outline_md"],
                evidence_item_ids=_load(row["evidence_item_ids"], []),
                final_score=row["final_score"],
                status=row["status"],
                generated_at=_dt(row["generated_at"]) or datetime.now(timezone.utc),
            )
            for row in rows
        ]

    def set_idea_status(self, idea_id: str, status: str) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE idea_cards SET status = %s WHERE id = %s", (status, idea_id))

    def publish_weekly_report(self, report: WeeklyReport) -> WeeklyReport:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO weekly_reports (
                        id, research_profile_id, report_period_start, report_period_end,
                        top_idea_ids, top_creator_ids, summary_md, published_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                    ON CONFLICT (research_profile_id, report_period_start, report_period_end) DO UPDATE SET
                        top_idea_ids = EXCLUDED.top_idea_ids,
                        top_creator_ids = EXCLUDED.top_creator_ids,
                        summary_md = EXCLUDED.summary_md,
                        published_at = EXCLUDED.published_at
                    """,
                    (
                        report.id,
                        report.research_profile_id,
                        _iso(report.report_period_start),
                        _iso(report.report_period_end),
                        _dump(report.top_idea_ids),
                        _dump(report.top_creator_ids),
                        report.summary_md,
                        _iso(report.published_at),
                    ),
                )
        return report

    def get_latest_report(self, research_profile_id: str) -> Optional[WeeklyReport]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM weekly_reports
                    WHERE research_profile_id = %s
                    ORDER BY published_at DESC
                    LIMIT 1
                    """,
                    (research_profile_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return WeeklyReport(
            id=row["id"],
            research_profile_id=row["research_profile_id"],
            report_period_start=_dt(row["report_period_start"]) or datetime.now(timezone.utc),
            report_period_end=_dt(row["report_period_end"]) or datetime.now(timezone.utc),
            top_idea_ids=_load(row["top_idea_ids"], []),
            top_creator_ids=_load(row["top_creator_ids"], []),
            summary_md=row["summary_md"],
            published_at=_dt(row["published_at"]) or datetime.now(timezone.utc),
        )

    def upsert_creator_watchlist(self, creators: List[CreatorWatch]) -> None:
        if not creators:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO creator_watchlists (
                        id, research_profile_id, source, creator_external_id, creator_name,
                        creator_url, watch_reason, watch_score, status, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (research_profile_id, source, creator_external_id) DO UPDATE SET
                        creator_name = EXCLUDED.creator_name,
                        creator_url = EXCLUDED.creator_url,
                        watch_reason = EXCLUDED.watch_reason,
                        watch_score = EXCLUDED.watch_score,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        (
                            creator.id,
                            creator.research_profile_id,
                            creator.source,
                            creator.creator_external_id,
                            creator.creator_name,
                            creator.creator_url,
                            creator.watch_reason,
                            creator.watch_score,
                            creator.status,
                            _iso(creator.updated_at),
                        )
                        for creator in creators
                    ],
                )

    def list_creator_watchlist(
        self,
        research_profile_id: str,
        limit: Optional[int] = None,
    ) -> List[CreatorWatch]:
        query = """
            SELECT * FROM creator_watchlists
            WHERE research_profile_id = %s
            ORDER BY watch_score DESC, updated_at DESC
        """
        params: list[Any] = [research_profile_id]
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [
            CreatorWatch(
                id=row["id"],
                research_profile_id=row["research_profile_id"],
                source=row["source"],
                creator_external_id=row["creator_external_id"],
                creator_name=row["creator_name"],
                creator_url=row["creator_url"],
                watch_reason=row["watch_reason"],
                watch_score=row["watch_score"],
                status=row["status"],
                updated_at=_dt(row["updated_at"]) or datetime.now(timezone.utc),
            )
            for row in rows
        ]

    def add_feedback(self, feedback: UserFeedbackEvent) -> UserFeedbackEvent:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_feedback_events (
                        id, research_profile_id, idea_card_id, event_type, event_payload, created_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        event_type = EXCLUDED.event_type,
                        event_payload = EXCLUDED.event_payload,
                        created_at = EXCLUDED.created_at
                    """,
                    (
                        feedback.id,
                        feedback.research_profile_id,
                        feedback.idea_card_id,
                        feedback.event_type,
                        _dump(feedback.event_payload),
                        _iso(feedback.created_at),
                    ),
                )
        return feedback

    def list_feedback(self, research_profile_id: str) -> List[UserFeedbackEvent]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM user_feedback_events
                    WHERE research_profile_id = %s
                    ORDER BY created_at ASC
                    """,
                    (research_profile_id,),
                )
                rows = cur.fetchall()
        return [
            UserFeedbackEvent(
                id=row["id"],
                research_profile_id=row["research_profile_id"],
                idea_card_id=row["idea_card_id"],
                event_type=row["event_type"],
                event_payload=_load(row["event_payload"], {}),
                created_at=_dt(row["created_at"]) or datetime.now(timezone.utc),
            )
            for row in rows
        ]

    def create_job_run(self, job: JobRun) -> JobRun:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO job_runs (
                        id, research_profile_id, job_type, status, scheduled_for, started_at,
                        finished_at, attempt_count, input_snapshot, error_summary,
                        next_run_at, heartbeat_at, lease_token, lease_owner, lease_expires_at, dispatched_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        scheduled_for = EXCLUDED.scheduled_for,
                        started_at = EXCLUDED.started_at,
                        finished_at = EXCLUDED.finished_at,
                        attempt_count = EXCLUDED.attempt_count,
                        input_snapshot = EXCLUDED.input_snapshot,
                        error_summary = EXCLUDED.error_summary,
                        next_run_at = EXCLUDED.next_run_at,
                        heartbeat_at = EXCLUDED.heartbeat_at,
                        lease_token = EXCLUDED.lease_token,
                        lease_owner = EXCLUDED.lease_owner,
                        lease_expires_at = EXCLUDED.lease_expires_at,
                        dispatched_at = EXCLUDED.dispatched_at
                    """,
                    (
                        job.id,
                        job.research_profile_id,
                        job.job_type.value,
                        job.status.value,
                        _iso(job.scheduled_for),
                        _iso(job.started_at),
                        _iso(job.finished_at),
                        job.attempt_count,
                        _dump(job.input_snapshot),
                        job.error_summary,
                        _iso(job.next_run_at),
                        _iso(job.heartbeat_at),
                        job.lease_token,
                        job.lease_owner,
                        _iso(job.lease_expires_at),
                        _iso(job.dispatched_at),
                    ),
                )
        return job

    def get_job(self, job_id: str) -> Optional[JobRun]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM job_runs WHERE id = %s", (job_id,))
                row = cur.fetchone()
        return self._row_to_job(row) if row else None

    def claim_due_job(self, now: datetime) -> Optional[JobRun]:
        claimed = self.claim_due_jobs(
            now,
            limit=1,
            lease_for=timedelta(minutes=15),
            lease_owner="local-scheduler",
        )
        return claimed[0] if claimed else None

    def claim_due_jobs(
        self,
        now: datetime,
        *,
        limit: int,
        lease_for: timedelta,
        lease_owner: str,
    ) -> List[JobRun]:
        lease_until = now + lease_for
        claimed: List[JobRun] = []
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM job_runs
                    WHERE (
                        status = %s AND scheduled_for <= %s
                    ) OR (
                        status = %s AND lease_expires_at IS NOT NULL AND lease_expires_at <= %s
                    )
                    ORDER BY scheduled_for ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                    """,
                    (
                        JobStatus.PENDING.value,
                        _iso(now),
                        JobStatus.RUNNING.value,
                        _iso(now),
                        max(1, limit),
                    ),
                )
                rows = cur.fetchall()
                for row in rows:
                    cur.execute(
                        """
                        UPDATE job_runs
                        SET status = %s,
                            started_at = COALESCE(started_at, %s),
                            finished_at = NULL,
                            heartbeat_at = %s,
                            attempt_count = attempt_count + 1,
                            error_summary = '',
                            lease_token = %s,
                            lease_owner = %s,
                            lease_expires_at = %s,
                            dispatched_at = NULL
                        WHERE id = %s
                        RETURNING *
                        """,
                        (
                            JobStatus.RUNNING.value,
                            _iso(now),
                            _iso(now),
                            uuid4().hex,
                            lease_owner,
                            _iso(lease_until),
                            row["id"],
                        ),
                    )
                    updated = cur.fetchone()
                    if updated:
                        claimed.append(self._row_to_job(updated))
        return claimed

    def mark_job_dispatched(self, job_id: str, dispatched_at: datetime) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE job_runs
                    SET dispatched_at = %s, heartbeat_at = COALESCE(heartbeat_at, %s)
                    WHERE id = %s
                    """,
                    (_iso(dispatched_at), _iso(dispatched_at), job_id),
                )

    def release_job(self, job_id: str, *, scheduled_for: Optional[datetime] = None) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE job_runs
                    SET status = %s,
                        scheduled_for = COALESCE(%s, scheduled_for),
                        lease_token = '',
                        lease_owner = '',
                        lease_expires_at = NULL,
                        dispatched_at = NULL
                    WHERE id = %s
                    """,
                    (JobStatus.PENDING.value, _iso(scheduled_for), job_id),
                )

    def complete_job(self, job_id: str, finished_at: datetime) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE job_runs
                    SET status = %s, finished_at = %s, heartbeat_at = %s,
                        lease_token = '', lease_owner = '', lease_expires_at = NULL
                    WHERE id = %s
                    """,
                    (JobStatus.SUCCEEDED.value, _iso(finished_at), _iso(finished_at), job_id),
                )

    def fail_job(self, job_id: str, finished_at: datetime, error_summary: str) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE job_runs
                    SET status = %s, finished_at = %s, heartbeat_at = %s, error_summary = %s,
                        lease_token = '', lease_owner = '', lease_expires_at = NULL
                    WHERE id = %s
                    """,
                    (JobStatus.FAILED.value, _iso(finished_at), _iso(finished_at), error_summary, job_id),
                )

    def has_open_job(self, research_profile_id: str, job_type: JobType) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM job_runs
                    WHERE research_profile_id = %s AND job_type = %s AND status IN (%s, %s)
                    LIMIT 1
                    """,
                    (
                        research_profile_id,
                        job_type.value,
                        JobStatus.PENDING.value,
                        JobStatus.RUNNING.value,
                    ),
                )
                row = cur.fetchone()
        return row is not None

    def list_jobs(self, research_profile_id: str, limit: int = 50) -> List[JobRun]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM job_runs
                    WHERE research_profile_id = %s
                    ORDER BY scheduled_for DESC
                    LIMIT %s
                    """,
                    (research_profile_id, limit),
                )
                rows = cur.fetchall()
        return [self._row_to_job(row) for row in rows]

    def _row_to_profile(self, row: dict[str, Any]) -> ResearchProfile:
        return ResearchProfile(
            id=row["id"],
            name=row["name"],
            persona_brief=row["persona_brief"],
            niche_definition=row["niche_definition"],
            must_track_topics=_load(row["must_track_topics"], []),
            excluded_topics=_load(row["excluded_topics"], []),
            target_audience=row["target_audience"],
            desired_formats=_load(row["desired_formats"], []),
            status=row["status"],
            created_at=_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=_dt(row["updated_at"]) or datetime.now(timezone.utc),
        )

    def _row_to_job(self, row: dict[str, Any]) -> JobRun:
        return JobRun(
            id=row["id"],
            research_profile_id=row["research_profile_id"],
            job_type=JobType(row["job_type"]),
            status=JobStatus(row["status"]),
            scheduled_for=_dt(row["scheduled_for"]) or datetime.now(timezone.utc),
            started_at=_dt(row["started_at"]),
            finished_at=_dt(row["finished_at"]),
            attempt_count=row["attempt_count"],
            input_snapshot=_load(row["input_snapshot"], {}),
            error_summary=row["error_summary"],
            next_run_at=_dt(row["next_run_at"]),
            heartbeat_at=_dt(row["heartbeat_at"]),
            lease_token=row.get("lease_token") or "",
            lease_owner=row.get("lease_owner") or "",
            lease_expires_at=_dt(row.get("lease_expires_at")),
            dispatched_at=_dt(row.get("dispatched_at")),
        )
