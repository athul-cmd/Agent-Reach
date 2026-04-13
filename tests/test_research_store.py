# -*- coding: utf-8 -*-
"""Tests for research storage."""

from datetime import timedelta

from agent_reach.research.models import (
    IdeaCard,
    JobRun,
    JobRunEvent,
    JobStatus,
    JobType,
    RefreshRequest,
    RefreshRequestStatus,
    ResearchProfile,
    WritingSample,
    utc_now,
)
from agent_reach.research.store import SQLiteResearchStore


def test_store_initializes_and_roundtrips_profile_and_samples(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")
    store.initialize()

    profile = ResearchProfile(
        name="Founder voice",
        persona_brief="Direct, analytical, operator-focused",
        niche_definition="AI product and content strategy",
        must_track_topics=["AI products", "content systems"],
        excluded_topics=["crypto"],
        target_audience="operators",
        desired_formats=["linkedin"],
    )
    store.upsert_profile(profile)

    sample = WritingSample(
        research_profile_id=profile.id,
        source_type="uploaded",
        title="Sample 1",
        raw_text="This is a long-form note about AI product positioning.",
    )
    store.add_writing_sample(sample)

    loaded = store.get_profile(profile.id)
    samples = store.list_writing_samples(profile.id)

    assert loaded is not None
    assert loaded.name == profile.name
    assert loaded.must_track_topics == profile.must_track_topics
    assert len(samples) == 1
    assert samples[0].title == "Sample 1"


def test_store_claims_due_jobs_and_updates_idea_status(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")
    store.initialize()

    profile = ResearchProfile(
        name="Ops",
        persona_brief="Operator",
        niche_definition="AI operations",
    )
    store.upsert_profile(profile)

    due_job = JobRun(
        research_profile_id=profile.id,
        job_type=JobType.COLLECT_SOURCES,
        status=JobStatus.PENDING,
        scheduled_for=utc_now() - timedelta(minutes=1),
    )
    store.create_job_run(due_job)

    claimed = store.claim_due_job(utc_now())
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING
    assert claimed.job_type == JobType.COLLECT_SOURCES

    idea = IdeaCard(
        research_profile_id=profile.id,
        topic_cluster_id="cluster_1",
        headline="Angle",
        hook="Hook",
        why_now="Why now",
        outline_md="- one\n- two",
        evidence_item_ids=[],
        final_score=0.7,
    )
    store.upsert_idea_cards([idea])
    store.set_idea_status(idea.id, "saved")
    saved = store.list_idea_cards(profile.id, status="saved")
    assert len(saved) == 1
    assert saved[0].id == idea.id


def test_store_claim_due_jobs_respects_limit_and_reclaims_expired_leases(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")
    store.initialize()

    profile = ResearchProfile(
        name="Ops",
        persona_brief="Operator",
        niche_definition="AI operations",
    )
    store.upsert_profile(profile)

    now = utc_now()
    due_one = JobRun(
        research_profile_id=profile.id,
        job_type=JobType.COLLECT_SOURCES,
        status=JobStatus.PENDING,
        scheduled_for=now - timedelta(minutes=10),
    )
    due_two = JobRun(
        research_profile_id=profile.id,
        job_type=JobType.DISCOVER_CREATORS,
        status=JobStatus.PENDING,
        scheduled_for=now - timedelta(minutes=5),
    )
    expired_running = JobRun(
        research_profile_id=profile.id,
        job_type=JobType.GENERATE_IDEAS,
        status=JobStatus.RUNNING,
        scheduled_for=now - timedelta(minutes=15),
        started_at=now - timedelta(minutes=15),
        attempt_count=1,
        lease_token="expired",
        lease_owner="scheduler-a",
        lease_expires_at=now - timedelta(minutes=1),
    )
    pending_later = JobRun(
        research_profile_id=profile.id,
        job_type=JobType.CLUSTER_ITEMS,
        status=JobStatus.PENDING,
        scheduled_for=now + timedelta(minutes=30),
    )
    for job in [due_one, due_two, expired_running, pending_later]:
        store.create_job_run(job)

    claimed = store.claim_due_jobs(
        now,
        limit=2,
        lease_for=timedelta(minutes=20),
        lease_owner="scheduler-b",
    )

    assert len(claimed) == 2
    assert {job.id for job in claimed} == {due_one.id, expired_running.id}
    assert all(job.status == JobStatus.RUNNING for job in claimed)
    assert all(job.lease_owner == "scheduler-b" for job in claimed)
    assert all(job.lease_token for job in claimed)
    assert store.get_job(expired_running.id).attempt_count == 2
    assert store.get_job(due_two.id).status == JobStatus.PENDING
    assert store.get_job(pending_later.id).status == JobStatus.PENDING


def test_store_release_job_returns_it_to_pending_and_clears_lease(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")
    store.initialize()

    profile = ResearchProfile(
        name="Ops",
        persona_brief="Operator",
        niche_definition="AI operations",
    )
    store.upsert_profile(profile)

    now = utc_now()
    job = JobRun(
        research_profile_id=profile.id,
        job_type=JobType.COLLECT_SOURCES,
        status=JobStatus.RUNNING,
        scheduled_for=now - timedelta(minutes=5),
        started_at=now - timedelta(minutes=5),
        attempt_count=1,
        lease_token="lease-token",
        lease_owner="scheduler-a",
        lease_expires_at=now + timedelta(minutes=10),
    )
    store.create_job_run(job)

    rescheduled_for = now + timedelta(minutes=15)
    store.release_job(job.id, scheduled_for=rescheduled_for)
    released = store.get_job(job.id)

    assert released is not None
    assert released.status == JobStatus.PENDING
    assert released.scheduled_for == rescheduled_for
    assert released.lease_token == ""
    assert released.lease_owner == ""
    assert released.lease_expires_at is None
    assert released.dispatched_at is None


def test_store_tracks_refresh_requests_events_and_dependency_aware_claims(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")
    store.initialize()

    profile = ResearchProfile(
        name="Ops",
        persona_brief="Operator",
        niche_definition="AI operations",
    )
    store.upsert_profile(profile)

    refresh = RefreshRequest(
        research_profile_id=profile.id,
        trigger="manual_full_refresh",
        status=RefreshRequestStatus.PENDING,
        query_snapshot={"queries": ["ai operations"]},
    )
    store.create_refresh_request(refresh)

    now = utc_now()
    collect_job = JobRun(
        research_profile_id=profile.id,
        refresh_request_id=refresh.id,
        job_type=JobType.COLLECT_SOURCES,
        status=JobStatus.PENDING,
        scheduled_for=now - timedelta(minutes=1),
    )
    idea_job = JobRun(
        research_profile_id=profile.id,
        refresh_request_id=refresh.id,
        job_type=JobType.GENERATE_IDEAS,
        status=JobStatus.PENDING,
        scheduled_for=now - timedelta(minutes=1),
        depends_on_job_run_id=collect_job.id,
    )
    store.create_job_run(collect_job)
    store.create_job_run(idea_job)

    claimed = store.claim_due_jobs(
        now,
        limit=5,
        lease_for=timedelta(minutes=20),
        lease_owner="scheduler",
    )
    assert [job.id for job in claimed] == [collect_job.id]

    store.add_job_event(
        JobRunEvent(
            refresh_request_id=refresh.id,
            job_run_id=collect_job.id,
            message="Collecting web results.",
            step="collecting",
            source="web",
            progress_current=1,
            progress_total=4,
        )
    )
    store.update_job_progress(
        collect_job.id,
        current_step="collecting",
        current_source="web",
        progress_current=1,
        progress_total=4,
        output_snapshot={"source_status": {"web": {"collected": 3}}},
    )
    store.complete_job(collect_job.id, utc_now(), output_snapshot={"collected": 3})

    refresh_events = store.list_job_events(refresh_request_id=refresh.id)
    assert len(refresh_events) == 1
    assert refresh_events[0].source == "web"

    next_claimed = store.claim_due_jobs(
        utc_now(),
        limit=5,
        lease_for=timedelta(minutes=20),
        lease_owner="scheduler",
    )
    assert [job.id for job in next_claimed] == [idea_job.id]

    store.update_refresh_request(
        refresh.id,
        status=RefreshRequestStatus.RUNNING,
        latest_stage="collect_sources",
        summary="Collecting sources.",
    )
    loaded_refresh = store.get_refresh_request(refresh.id)
    assert loaded_refresh is not None
    assert loaded_refresh.status == RefreshRequestStatus.RUNNING
    assert loaded_refresh.latest_stage == "collect_sources"
