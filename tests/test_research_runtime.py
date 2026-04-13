# -*- coding: utf-8 -*-
"""Tests for the persistent research worker runtime wrapper."""

from pathlib import Path

from agent_reach.research.models import ResearchProfile
from agent_reach.research.runtime import ResearchWorkerService, load_worker_status
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store import SQLiteResearchStore
from agent_reach.research.worker import ResearchScheduler, ResearchWorker


class _NoopWorker(ResearchWorker):
    def __init__(self, store, settings):
        super().__init__(store=store, settings=settings, adapters=[])


class _StubScheduler:
    def __init__(self, result=None):
        self.result = result
        self.ticks = 0

    def tick(self, profile_id: str):
        self.ticks += 1
        return self.result


def _settings(tmp_path: Path) -> ResearchSettings:
    return ResearchSettings(
        db_backend="sqlite",
        db_path=str(tmp_path / "research.db"),
        db_dsn="",
        blob_backend="local",
        blob_root_dir=str(tmp_path / "blobs"),
        blob_bucket="",
        blob_prefix="agent-reach/research",
        raw_artifact_dir=str(tmp_path / "raw"),
        snapshot_dir=str(tmp_path / "snapshots"),
        runtime_dir=str(tmp_path / "runtime"),
    )


def test_worker_service_records_idle_status_without_profile(tmp_path):
    settings = _settings(tmp_path)
    store = SQLiteResearchStore(settings.db_path)
    worker = _NoopWorker(store=store, settings=settings)
    scheduler = _StubScheduler()
    service = ResearchWorkerService(
        store=store,
        settings=settings,
        worker=worker,
        scheduler=scheduler,  # type: ignore[arg-type]
        sleep_seconds=1,
    )

    service.initialize()
    service.run_forever(max_ticks=1)

    payload = load_worker_status(settings)

    assert payload is not None
    assert payload["state"] == "stopped"
    assert payload["active_profile_id"] is None
    assert payload["tick_count"] == 1
    assert scheduler.ticks == 0


def test_worker_service_runs_one_tick_for_latest_profile(tmp_path):
    settings = _settings(tmp_path)
    store = SQLiteResearchStore(settings.db_path)
    profile = ResearchProfile(
        name="Researcher",
        persona_brief="Operator-led",
        niche_definition="AI content systems",
    )
    store.initialize()
    store.upsert_profile(profile)
    worker = _NoopWorker(store=store, settings=settings)
    scheduler = _StubScheduler(result={"job": "collect_sources", "result": {"collected": 3}})
    service = ResearchWorkerService(
        store=store,
        settings=settings,
        worker=worker,
        scheduler=scheduler,  # type: ignore[arg-type]
        sleep_seconds=1,
    )

    service.initialize()
    service.run_forever(max_ticks=1)

    payload = load_worker_status(settings)

    assert payload is not None
    assert payload["state"] == "stopped"
    assert payload["active_profile_id"] == profile.id
    assert payload["last_result"]["job"] == "collect_sources"
    assert scheduler.ticks == 1
