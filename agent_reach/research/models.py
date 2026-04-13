# -*- coding: utf-8 -*-
"""Domain models for the content research studio."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Generate a readable object identifier."""
    return f"{prefix}_{uuid4().hex[:12]}"


class JobType(str, Enum):
    """Supported background jobs."""

    COLLECT_SOURCES = "collect_sources"
    DISCOVER_CREATORS = "discover_creators"
    REFRESH_STYLE_PROFILE = "refresh_style_profile"
    CLUSTER_ITEMS = "cluster_items"
    RANK_TOPICS = "rank_topics"
    GENERATE_IDEAS = "generate_ideas"
    PUBLISH_WEEKLY_DIGEST = "publish_weekly_digest"


class JobStatus(str, Enum):
    """Lifecycle states for background jobs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class RefreshRequestStatus(str, Enum):
    """Lifecycle states for one tracked full refresh pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(slots=True)
class ResearchProfile:
    """Canonical user-authored scope definition."""

    name: str
    persona_brief: str
    niche_definition: str
    must_track_topics: List[str] = field(default_factory=list)
    excluded_topics: List[str] = field(default_factory=list)
    target_audience: str = ""
    desired_formats: List[str] = field(default_factory=list)
    status: str = "active"
    id: str = field(default_factory=lambda: new_id("profile"))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class WritingSample:
    """Uploaded or imported authored writing."""

    research_profile_id: str
    source_type: str
    title: str
    raw_text: str
    raw_blob_url: str = ""
    language: str = "en"
    id: str = field(default_factory=lambda: new_id("sample"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class StyleProfile:
    """Learned writing profile."""

    research_profile_id: str
    tone_markers: List[str] = field(default_factory=list)
    hook_patterns: List[str] = field(default_factory=list)
    structure_patterns: List[str] = field(default_factory=list)
    preferred_topics: List[str] = field(default_factory=list)
    avoided_topics: List[str] = field(default_factory=list)
    evidence_preferences: List[str] = field(default_factory=list)
    embedding_version: str = "heuristic-v1"
    raw_summary: str = ""
    id: str = field(default_factory=lambda: new_id("style"))
    generated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class CreatorWatch:
    """Tracked account or creator worth monitoring."""

    research_profile_id: str
    source: str
    creator_external_id: str
    creator_name: str
    creator_url: str
    watch_reason: str
    watch_score: float
    status: str = "active"
    id: str = field(default_factory=lambda: new_id("creator"))
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class SourceItem:
    """Normalized source artifact collected from a platform."""

    research_profile_id: str
    source: str
    external_id: str
    canonical_url: str
    author_name: str
    published_at: datetime
    title: str
    body_text: str
    engagement: Dict[str, Any] = field(default_factory=dict)
    raw_blob_url: str = ""
    health_status: str = "ok"
    source_query: str = ""
    id: str = field(default_factory=lambda: new_id("item"))
    created_at: datetime = field(default_factory=utc_now)

    def combined_text(self) -> str:
        """Return title and body for text scoring."""
        if self.body_text:
            return f"{self.title}\n{self.body_text}"
        return self.title


@dataclass(slots=True)
class TopicCluster:
    """Semantic grouping of source items."""

    research_profile_id: str
    cluster_label: str
    cluster_summary: str
    representative_terms: List[str]
    supporting_item_ids: List[str]
    source_family_count: int
    freshness_score: float
    cluster_key: str
    final_score: float = 0.0
    score_components: Dict[str, float] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("cluster"))
    rank_snapshot_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class IdeaCard:
    """Ranked idea candidate derived from a cluster."""

    research_profile_id: str
    topic_cluster_id: str
    headline: str
    hook: str
    why_now: str
    outline_md: str
    evidence_item_ids: List[str]
    final_score: float
    status: str = "new"
    id: str = field(default_factory=lambda: new_id("idea"))
    generated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class WeeklyReport:
    """Published weekly digest."""

    research_profile_id: str
    report_period_start: datetime
    report_period_end: datetime
    top_idea_ids: List[str]
    top_creator_ids: List[str]
    summary_md: str
    id: str = field(default_factory=lambda: new_id("report"))
    published_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class UserFeedbackEvent:
    """Saved/discarded/feedback action."""

    research_profile_id: str
    idea_card_id: str
    event_type: str
    event_payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("feedback"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class JobRun:
    """Background job execution record."""

    research_profile_id: str
    job_type: JobType
    status: JobStatus
    scheduled_for: datetime
    refresh_request_id: str = ""
    depends_on_job_run_id: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    attempt_count: int = 0
    input_snapshot: Dict[str, Any] = field(default_factory=dict)
    output_snapshot: Dict[str, Any] = field(default_factory=dict)
    current_step: str = ""
    current_source: str = ""
    progress_current: int = 0
    progress_total: int = 0
    error_summary: str = ""
    next_run_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None
    lease_token: str = ""
    lease_owner: str = ""
    lease_expires_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: new_id("job"))


@dataclass(slots=True)
class RefreshRequest:
    """One tracked manual or scheduled refresh request."""

    research_profile_id: str
    trigger: str
    status: RefreshRequestStatus
    query_snapshot: Dict[str, Any] = field(default_factory=dict)
    latest_stage: str = ""
    summary: str = ""
    source_status: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    id: str = field(default_factory=lambda: new_id("refresh"))


@dataclass(slots=True)
class JobRunEvent:
    """Progress/event log emitted while a refresh pipeline executes."""

    job_run_id: str
    message: str
    refresh_request_id: str = ""
    level: str = "info"
    step: str = ""
    source: str = ""
    progress_current: int = 0
    progress_total: int = 0
    event_payload: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    id: str = field(default_factory=lambda: new_id("event"))
