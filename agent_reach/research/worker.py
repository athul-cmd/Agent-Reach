# -*- coding: utf-8 -*-
"""Research worker and scheduler foundations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Sequence
from zoneinfo import ZoneInfo

from agent_reach.research.artifacts import write_snapshot_artifact
from agent_reach.research.adapters.base import SourceAdapter
from agent_reach.research.adapters.sources import (
    RedditAdapter,
    WebExaAdapter,
    XAdapter,
    YouTubeAdapter,
)
from agent_reach.research.clustering import cluster_source_items
from agent_reach.research.models import (
    CreatorWatch,
    IdeaCard,
    JobRun,
    JobRunEvent,
    JobStatus,
    JobType,
    ResearchProfile,
    WeeklyReport,
    utc_now,
)
from agent_reach.research.openai_client import OpenAIResearchClient
from agent_reach.research.scoring import build_cluster_score, compute_final_score
from agent_reach.research.secrets import resolve_openai_api_key
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.snapshot import serialize_nodepad_snapshot
from agent_reach.research.store_protocol import ResearchStore
from agent_reach.research.style import build_style_profile
from agent_reach.research.planner import build_query_snapshot


def _resolve_tz(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _next_daily(hour: int, tz_name: str) -> datetime:
    local_tz = _resolve_tz(tz_name)
    now_local = datetime.now(local_tz)
    target = now_local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now_local:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


def _next_weekly(weekday: int, hour: int, tz_name: str) -> datetime:
    local_tz = _resolve_tz(tz_name)
    now_local = datetime.now(local_tz)
    target = now_local.replace(hour=hour, minute=0, second=0, microsecond=0)
    days_ahead = (weekday - target.weekday()) % 7
    if days_ahead == 0 and target <= now_local:
        days_ahead = 7
    return (target + timedelta(days=days_ahead)).astimezone(timezone.utc)


class ResearchWorker:
    """Owns collection, learning, clustering, ranking, and digest generation."""

    def __init__(
        self,
        store: ResearchStore,
        settings: ResearchSettings,
        openai_client: OpenAIResearchClient | None = None,
        adapters: Sequence[SourceAdapter] | None = None,
    ):
        self.store = store
        self.settings = settings
        effective_api_key = resolve_openai_api_key(settings)
        if effective_api_key:
            self.settings.openai_api_key = effective_api_key
        self.openai_client = openai_client or OpenAIResearchClient(
            api_key=self.settings.openai_api_key,
            base_url=settings.openai_base_url,
            chat_model=settings.chat_model,
            embedding_model=settings.embedding_model,
        )
        self.adapters = list(adapters or self._default_adapters())
        self._active_job: JobRun | None = None

    def _default_adapters(self) -> List[SourceAdapter]:
        return [WebExaAdapter(), RedditAdapter(), YouTubeAdapter(), XAdapter()]

    def initialize(self) -> None:
        """Prepare persistent storage and local dirs."""
        self.settings.ensure_dirs()
        self.store.initialize()

    def run_job(self, job_type: JobType, profile_id: str, *, job_run_id: str = "") -> dict:
        """Run a single worker job."""
        handlers = {
            JobType.COLLECT_SOURCES: self.collect_sources,
            JobType.DISCOVER_CREATORS: self.discover_creators,
            JobType.REFRESH_STYLE_PROFILE: self.refresh_style_profile,
            JobType.CLUSTER_ITEMS: self.cluster_items,
            JobType.RANK_TOPICS: self.rank_topics,
            JobType.GENERATE_IDEAS: self.generate_ideas,
            JobType.PUBLISH_WEEKLY_DIGEST: self.publish_weekly_digest,
        }
        if job_type not in handlers:
            raise ValueError(f"Unsupported job: {job_type}")
        previous_job = self._active_job
        self._active_job = self.store.get_job(job_run_id) if job_run_id else None
        try:
            self._set_progress("starting", progress_current=0, progress_total=1)
            self._emit_event(f"Starting {job_type.value}.", step="starting")
            return handlers[job_type](profile_id)
        finally:
            self._active_job = previous_job

    def run_full_cycle(self, profile_id: str) -> dict:
        """Run the core daily pipeline sequentially."""
        results = {}
        for job_type in (
            JobType.COLLECT_SOURCES,
            JobType.DISCOVER_CREATORS,
            JobType.REFRESH_STYLE_PROFILE,
            JobType.CLUSTER_ITEMS,
            JobType.RANK_TOPICS,
            JobType.GENERATE_IDEAS,
        ):
            results[job_type.value] = self.run_job(job_type, profile_id)
        return results

    def collect_sources(self, profile_id: str) -> dict:
        profile = self._require_profile(profile_id)
        query_snapshot = build_query_snapshot(profile)
        collected = []
        failures = []
        per_source: dict[str, dict] = {}
        total_sources = len(self.adapters)
        self._set_progress("collecting", progress_current=0, progress_total=total_sources)
        for index, adapter in enumerate(self.adapters, start=1):
            self._set_progress(
                "collecting",
                current_source=adapter.source_name,
                progress_current=index - 1,
                progress_total=total_sources,
                output_snapshot={
                    "queries": query_snapshot["queries"],
                    "source_status": per_source,
                },
            )
            self._emit_event(
                f"Collecting {adapter.source_name} results.",
                step="collecting",
                source=adapter.source_name,
                progress_current=index - 1,
                progress_total=total_sources,
            )
            if not adapter.is_available():
                failure = {"source": adapter.source_name, "status": "unavailable", "error": "adapter unavailable"}
                failures.append(f"{adapter.source_name}: unavailable")
                per_source[adapter.source_name] = failure
                self._emit_event(
                    f"{adapter.source_name} is unavailable on this runner.",
                    level="warning",
                    step="collecting",
                    source=adapter.source_name,
                    progress_current=index,
                    progress_total=total_sources,
                    event_payload=failure,
                )
                continue
            try:
                source_items = adapter.collect(profile, self.settings, self.settings.source_result_limit)
                collected.extend(source_items)
                per_source[adapter.source_name] = {
                    "source": adapter.source_name,
                    "status": "ok",
                    "collected": len(source_items),
                }
                self._emit_event(
                    f"Collected {len(source_items)} items from {adapter.source_name}.",
                    step="collecting",
                    source=adapter.source_name,
                    progress_current=index,
                    progress_total=total_sources,
                    event_payload=per_source[adapter.source_name],
                )
            except Exception as exc:
                failures.append(f"{adapter.source_name}: {exc}")
                per_source[adapter.source_name] = {
                    "source": adapter.source_name,
                    "status": "failed",
                    "error": str(exc),
                }
                self._emit_event(
                    f"{adapter.source_name} collection failed.",
                    level="warning",
                    step="collecting",
                    source=adapter.source_name,
                    progress_current=index,
                    progress_total=total_sources,
                    event_payload=per_source[adapter.source_name],
                )
                continue
            self._set_progress(
                "collecting",
                current_source=adapter.source_name,
                progress_current=index,
                progress_total=total_sources,
                output_snapshot={
                    "queries": query_snapshot["queries"],
                    "source_status": per_source,
                },
            )
        self.store.upsert_source_items(collected)
        result = {
            "queries": query_snapshot["queries"],
            "collected": len(collected),
            "source_status": per_source,
            "failures": failures,
        }
        self._set_progress(
            "collecting",
            current_source="",
            progress_current=total_sources,
            progress_total=total_sources,
            output_snapshot=result,
        )
        return result

    def discover_creators(self, profile_id: str) -> dict:
        self._set_progress("discovering_creators", progress_current=0, progress_total=1)
        items = self.store.list_source_items(profile_id, limit=250)
        grouped = defaultdict(list)
        for item in items:
            key = (item.source, item.author_name)
            grouped[key].append(item)
        creators = []
        for (source, author), author_items in grouped.items():
            creator_url = next((item.canonical_url for item in author_items if item.canonical_url), "")
            watch_score = min(1.0, len(author_items) / 5.0)
            creators.append(
                CreatorWatch(
                    research_profile_id=profile_id,
                    source=source,
                    creator_external_id=f"{source}:{author}",
                    creator_name=author,
                    creator_url=creator_url,
                    watch_reason=f"Observed in {len(author_items)} recent source items.",
                    watch_score=watch_score,
                )
            )
        self.store.upsert_creator_watchlist(creators)
        result = {"creators": len(creators)}
        self._set_progress("discovering_creators", progress_current=1, progress_total=1, output_snapshot=result)
        self._emit_event("Creator discovery completed.", step="discovering_creators", progress_current=1, progress_total=1, event_payload=result)
        return result

    def refresh_style_profile(self, profile_id: str) -> dict:
        self._set_progress("refreshing_style", progress_current=0, progress_total=1)
        profile = self._require_profile(profile_id)
        samples = self.store.list_writing_samples(profile_id)
        feedback = self.store.list_feedback(profile_id)
        style_profile = build_style_profile(profile, samples, feedback, self.openai_client)
        self.store.upsert_style_profile(style_profile)
        result = {
            "style_profile_id": style_profile.id,
            "sample_count": len(samples),
            "feedback_count": len(feedback),
        }
        self._set_progress("refreshing_style", progress_current=1, progress_total=1, output_snapshot=result)
        self._emit_event("Style profile refreshed.", step="refreshing_style", progress_current=1, progress_total=1, event_payload=result)
        return result

    def cluster_items(self, profile_id: str) -> dict:
        self._set_progress("clustering", progress_current=0, progress_total=1)
        profile = self._require_profile(profile_id)
        items = self.store.list_source_items(profile_id, limit=500)
        clusters = cluster_source_items(profile, items)
        self.store.upsert_clusters(clusters)
        result = {"clusters": len(clusters), "items": len(items)}
        self._set_progress("clustering", progress_current=1, progress_total=1, output_snapshot=result)
        self._emit_event("Clustering completed.", step="clustering", progress_current=1, progress_total=1, event_payload=result)
        return result

    def rank_topics(self, profile_id: str) -> dict:
        self._set_progress("ranking", progress_current=0, progress_total=1)
        profile = self._require_profile(profile_id)
        style_profile = self.store.get_latest_style_profile(profile_id)
        items = self.store.list_source_items(profile_id, limit=500)
        clusters = self.store.list_clusters(profile_id)
        recent_ideas = [idea.headline for idea in self.store.list_idea_cards(profile_id, limit=25)]

        for cluster in clusters:
            components = build_cluster_score(profile, style_profile, cluster, items, recent_ideas)
            cluster.score_components = components.as_dict()
            cluster.final_score = compute_final_score(components)
            cluster.rank_snapshot_at = utc_now()
        self.store.upsert_clusters(clusters)
        result = {"ranked_clusters": len(clusters)}
        self._set_progress("ranking", progress_current=1, progress_total=1, output_snapshot=result)
        self._emit_event("Topic ranking completed.", step="ranking", progress_current=1, progress_total=1, event_payload=result)
        return result

    def generate_ideas(self, profile_id: str) -> dict:
        self._set_progress("generating_ideas", progress_current=0, progress_total=1)
        clusters = self.store.list_clusters(profile_id)[:10]
        ideas = []
        for cluster in clusters:
            ideas.append(self._idea_from_cluster(cluster, profile_id))
        self.store.upsert_idea_cards(ideas)
        result = {
            "ideas": len(ideas),
            "cluster_ids": [cluster.id for cluster in clusters],
            "evidence_item_ids": sorted({item_id for idea in ideas for item_id in idea.evidence_item_ids}),
            "model": self.settings.chat_model if self.openai_client.available else "heuristic",
        }
        self._set_progress("generating_ideas", progress_current=1, progress_total=1, output_snapshot=result)
        self._emit_event("Idea generation completed.", step="generating_ideas", progress_current=1, progress_total=1, event_payload=result)
        return result

    def publish_weekly_digest(self, profile_id: str) -> dict:
        self._set_progress("publishing_digest", progress_current=0, progress_total=1)
        ideas = self.store.list_idea_cards(profile_id, limit=10)
        creators = self.store.list_creator_watchlist(profile_id, limit=10)
        now = utc_now()
        report = WeeklyReport(
            research_profile_id=profile_id,
            report_period_start=now - timedelta(days=7),
            report_period_end=now,
            top_idea_ids=[idea.id for idea in ideas[:5]],
            top_creator_ids=[creator.id for creator in creators[:5]],
            summary_md=self._weekly_summary(ideas[:5], creators[:5]),
        )
        self.store.publish_weekly_report(report)
        cluster_ids = {idea.topic_cluster_id for idea in ideas}
        clusters = [cluster for cluster in self.store.list_clusters(profile_id) if cluster.id in cluster_ids]
        snapshot_uri = write_snapshot_artifact(
            settings=self.settings,
            profile_id=profile_id,
            report_id=report.id,
            payload_text=serialize_nodepad_snapshot(report, ideas, clusters),
            published_at=report.published_at,
        )
        result = {"report_id": report.id, "snapshot_path": snapshot_uri}
        self._set_progress("publishing_digest", progress_current=1, progress_total=1, output_snapshot=result)
        self._emit_event("Weekly digest published.", step="publishing_digest", progress_current=1, progress_total=1, event_payload=result)
        return result

    def _idea_from_cluster(self, cluster, profile_id: str) -> IdeaCard:
        if self.openai_client.available:
            try:
                data = self.openai_client.chat_json(
                    system_prompt=(
                        "You generate concise structured content research ideas. "
                        "Return JSON with headline, hook, why_now, outline_md."
                    ),
                    user_prompt=(
                        f"Cluster label: {cluster.cluster_label}\n"
                        f"Cluster summary: {cluster.cluster_summary}\n"
                        f"Representative terms: {cluster.representative_terms}\n"
                        f"Score: {cluster.final_score}"
                    ),
                )
                return IdeaCard(
                    research_profile_id=profile_id,
                    topic_cluster_id=cluster.id,
                    headline=str(data.get("headline") or cluster.cluster_label),
                    hook=str(data.get("hook") or f"Why {cluster.cluster_label} is accelerating now"),
                    why_now=str(data.get("why_now") or cluster.cluster_summary),
                    outline_md=str(
                        data.get("outline_md")
                        or f"- Lead with the signal behind {cluster.cluster_label}\n"
                        f"- Explain why it matters now\n- Offer one concrete angle"
                    ),
                    evidence_item_ids=list(cluster.supporting_item_ids),
                    final_score=cluster.final_score,
                )
            except Exception:
                pass
        terms = ", ".join(cluster.representative_terms[:3])
        return IdeaCard(
            research_profile_id=profile_id,
            topic_cluster_id=cluster.id,
            headline=f"{cluster.cluster_label}: a timely angle for your niche",
            hook=f"A repeated public signal is surfacing around {cluster.cluster_label.lower()}.",
            why_now=cluster.cluster_summary,
            outline_md=(
                f"- Open with the signal: {cluster.cluster_label}\n"
                f"- Tie it to your niche via {terms or 'recent evidence'}\n"
                "- Explain what changed recently\n"
                "- Close with a practical takeaway or position"
            ),
            evidence_item_ids=list(cluster.supporting_item_ids),
            final_score=cluster.final_score,
        )

    def _weekly_summary(self, ideas: Sequence[IdeaCard], creators: Sequence[CreatorWatch]) -> str:
        lines = ["## Weekly Digest", "", "### Top ideas"]
        for idea in ideas:
            lines.append(f"- **{idea.headline}**: {idea.hook}")
        lines.append("")
        lines.append("### Creators worth watching")
        for creator in creators:
            lines.append(f"- **{creator.creator_name}** ({creator.source}): {creator.watch_reason}")
        return "\n".join(lines)

    def _require_profile(self, profile_id: str) -> ResearchProfile:
        profile = self.store.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Unknown research profile: {profile_id}")
        return profile

    def _set_progress(
        self,
        step: str,
        *,
        current_source: str = "",
        progress_current: int,
        progress_total: int,
        output_snapshot: dict | None = None,
    ) -> None:
        if self._active_job is None:
            return
        self.store.update_job_progress(
            self._active_job.id,
            current_step=step,
            current_source=current_source,
            progress_current=progress_current,
            progress_total=progress_total,
            heartbeat_at=utc_now(),
            output_snapshot=output_snapshot,
        )

    def _emit_event(
        self,
        message: str,
        *,
        level: str = "info",
        step: str = "",
        source: str = "",
        progress_current: int = 0,
        progress_total: int = 0,
        event_payload: dict | None = None,
    ) -> None:
        if self._active_job is None:
            return
        self.store.add_job_event(
            JobRunEvent(
                job_run_id=self._active_job.id,
                refresh_request_id=self._active_job.refresh_request_id,
                level=level,
                message=message,
                step=step,
                source=source,
                progress_current=progress_current,
                progress_total=progress_total,
                event_payload=event_payload or {},
            )
        )


class ResearchScheduler:
    """Persistent scheduler that reconciles recurring jobs."""

    def __init__(self, store: ResearchStore, settings: ResearchSettings, worker: ResearchWorker):
        self.store = store
        self.settings = settings
        self.worker = worker

    def bootstrap_profile(self, profile_id: str, now: datetime | None = None) -> None:
        """Ensure recurring jobs exist for a profile."""
        now = now or utc_now()
        desired = {
            JobType.COLLECT_SOURCES: now,
            JobType.DISCOVER_CREATORS: now + timedelta(minutes=1),
            JobType.REFRESH_STYLE_PROFILE: _next_daily(
                self.settings.daily_synthesis_hour,
                self.settings.timezone,
            ),
            JobType.CLUSTER_ITEMS: _next_daily(
                self.settings.daily_synthesis_hour,
                self.settings.timezone,
            ),
            JobType.RANK_TOPICS: _next_daily(
                self.settings.daily_synthesis_hour,
                self.settings.timezone,
            ),
            JobType.GENERATE_IDEAS: _next_daily(
                self.settings.daily_synthesis_hour,
                self.settings.timezone,
            ),
            JobType.PUBLISH_WEEKLY_DIGEST: _next_weekly(
                self.settings.weekly_digest_weekday,
                self.settings.weekly_digest_hour,
                self.settings.timezone,
            ),
        }
        for job_type, scheduled_for in desired.items():
            if not self.store.has_open_job(profile_id, job_type):
                self.store.create_job_run(
                    JobRun(
                        research_profile_id=profile_id,
                        job_type=job_type,
                        status=JobStatus.PENDING,
                        scheduled_for=scheduled_for,
                    )
                )

    def tick(self, profile_id: str, now: datetime | None = None) -> dict | None:
        """Run one due job if available."""
        now = now or utc_now()
        self.bootstrap_profile(profile_id, now)
        job = self.store.claim_due_job(now)
        if job is None:
            return None
        try:
            result = self.worker.run_job(job.job_type, job.research_profile_id)
            self.store.complete_job(job.id, utc_now())
            self.store.create_job_run(
                JobRun(
                    research_profile_id=job.research_profile_id,
                    job_type=job.job_type,
                    status=JobStatus.PENDING,
                    scheduled_for=self._next_time(job.job_type, now),
                )
            )
            return {"job": job.job_type.value, "result": result}
        except Exception as exc:
            self.store.fail_job(job.id, utc_now(), str(exc))
            retry_at = now + timedelta(minutes=10)
            self.store.create_job_run(
                JobRun(
                    research_profile_id=job.research_profile_id,
                    job_type=job.job_type,
                    status=JobStatus.PENDING,
                    scheduled_for=retry_at,
                    input_snapshot={"retry_of": job.id},
                )
            )
            return {"job": job.job_type.value, "error": str(exc)}

    def _next_time(self, job_type: JobType, now: datetime) -> datetime:
        if job_type in (JobType.COLLECT_SOURCES, JobType.DISCOVER_CREATORS):
            return now + timedelta(seconds=self.settings.collection_interval_seconds)
        if job_type in (
            JobType.REFRESH_STYLE_PROFILE,
            JobType.CLUSTER_ITEMS,
            JobType.RANK_TOPICS,
            JobType.GENERATE_IDEAS,
        ):
            return _next_daily(self.settings.daily_synthesis_hour, self.settings.timezone)
        return _next_weekly(
            self.settings.weekly_digest_weekday,
            self.settings.weekly_digest_hour,
            self.settings.timezone,
        )
