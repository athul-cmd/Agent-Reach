# -*- coding: utf-8 -*-
"""Tests for research scheduler behavior."""

from agent_reach.research.models import ResearchProfile, utc_now
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store import SQLiteResearchStore
from agent_reach.research.worker import ResearchScheduler


class _DummyWorker:
    def __init__(self):
        self.calls = []

    def run_job(self, job_type, profile_id):
        self.calls.append((job_type, profile_id))
        return {"ok": True}


def test_scheduler_bootstraps_and_runs_due_job(tmp_path):
    store = SQLiteResearchStore(tmp_path / "research.db")
    store.initialize()
    profile = ResearchProfile(
        name="Researcher",
        persona_brief="Analytical",
        niche_definition="AI strategy",
    )
    store.upsert_profile(profile)

    settings = ResearchSettings.default()
    settings.db_path = str(tmp_path / "research.db")
    dummy = _DummyWorker()
    scheduler = ResearchScheduler(store=store, settings=settings, worker=dummy)

    result = scheduler.tick(profile.id, utc_now())

    assert result is not None
    assert dummy.calls
    jobs = store.list_jobs(profile.id)
    assert jobs
    assert any(job.status.value in {"pending", "succeeded"} for job in jobs)
