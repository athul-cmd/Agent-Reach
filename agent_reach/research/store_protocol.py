# -*- coding: utf-8 -*-
"""Store protocol for research persistence backends."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Protocol

from agent_reach.research.models import (
    CreatorWatch,
    IdeaCard,
    JobRun,
    JobRunEvent,
    JobType,
    RefreshRequest,
    RefreshRequestStatus,
    ResearchProfile,
    SourceItem,
    StyleProfile,
    TopicCluster,
    UserFeedbackEvent,
    WeeklyReport,
    WritingSample,
)


class ResearchStore(Protocol):
    """Persistence contract shared by the API layer, worker, and CLI."""

    def initialize(self) -> None: ...

    def upsert_profile(self, profile: ResearchProfile) -> ResearchProfile: ...

    def get_profile(self, profile_id: str) -> Optional[ResearchProfile]: ...

    def get_latest_profile(self) -> Optional[ResearchProfile]: ...

    def add_writing_sample(self, sample: WritingSample) -> WritingSample: ...

    def list_writing_samples(self, research_profile_id: str) -> List[WritingSample]: ...

    def upsert_style_profile(self, style_profile: StyleProfile) -> StyleProfile: ...

    def get_latest_style_profile(self, research_profile_id: str) -> Optional[StyleProfile]: ...

    def upsert_source_items(self, items: List[SourceItem]) -> None: ...

    def list_source_items(self, research_profile_id: str, limit: Optional[int] = None) -> List[SourceItem]: ...

    def upsert_clusters(self, clusters: List[TopicCluster]) -> None: ...

    def list_clusters(self, research_profile_id: str) -> List[TopicCluster]: ...

    def upsert_idea_cards(self, ideas: List[IdeaCard]) -> None: ...

    def list_idea_cards(
        self,
        research_profile_id: str,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[IdeaCard]: ...

    def set_idea_status(self, idea_id: str, status: str) -> None: ...

    def publish_weekly_report(self, report: WeeklyReport) -> WeeklyReport: ...

    def get_latest_report(self, research_profile_id: str) -> Optional[WeeklyReport]: ...

    def upsert_creator_watchlist(self, creators: List[CreatorWatch]) -> None: ...

    def list_creator_watchlist(
        self,
        research_profile_id: str,
        limit: Optional[int] = None,
    ) -> List[CreatorWatch]: ...

    def add_feedback(self, feedback: UserFeedbackEvent) -> UserFeedbackEvent: ...

    def list_feedback(self, research_profile_id: str) -> List[UserFeedbackEvent]: ...

    def create_refresh_request(self, refresh_request: RefreshRequest) -> RefreshRequest: ...

    def get_refresh_request(self, refresh_request_id: str) -> Optional[RefreshRequest]: ...

    def list_refresh_requests(
        self,
        research_profile_id: str,
        limit: int = 10,
    ) -> List[RefreshRequest]: ...

    def update_refresh_request(
        self,
        refresh_request_id: str,
        *,
        status: Optional[RefreshRequestStatus] = None,
        latest_stage: Optional[str] = None,
        summary: Optional[str] = None,
        source_status: Optional[dict] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None: ...

    def create_job_run(self, job: JobRun) -> JobRun: ...

    def get_job(self, job_id: str) -> Optional[JobRun]: ...

    def list_jobs_for_refresh(self, refresh_request_id: str) -> List[JobRun]: ...

    def claim_due_job(self, now: datetime) -> Optional[JobRun]: ...

    def claim_due_jobs(
        self,
        now: datetime,
        *,
        limit: int,
        lease_for: timedelta,
        lease_owner: str,
    ) -> List[JobRun]: ...

    def mark_job_dispatched(self, job_id: str, dispatched_at: datetime) -> None: ...

    def update_job_progress(
        self,
        job_id: str,
        *,
        current_step: Optional[str] = None,
        current_source: Optional[str] = None,
        progress_current: Optional[int] = None,
        progress_total: Optional[int] = None,
        heartbeat_at: Optional[datetime] = None,
        output_snapshot: Optional[dict] = None,
    ) -> None: ...

    def add_job_event(self, event: JobRunEvent) -> JobRunEvent: ...

    def list_job_events(
        self,
        *,
        refresh_request_id: Optional[str] = None,
        job_run_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[JobRunEvent]: ...

    def release_job(self, job_id: str, *, scheduled_for: Optional[datetime] = None) -> None: ...

    def complete_job(
        self,
        job_id: str,
        finished_at: datetime,
        *,
        output_snapshot: Optional[dict] = None,
    ) -> None: ...

    def fail_job(
        self,
        job_id: str,
        finished_at: datetime,
        error_summary: str,
        *,
        output_snapshot: Optional[dict] = None,
    ) -> None: ...

    def has_open_job(self, research_profile_id: str, job_type: JobType) -> bool: ...

    def list_jobs(self, research_profile_id: str, limit: int = 50) -> List[JobRun]: ...
