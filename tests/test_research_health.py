# -*- coding: utf-8 -*-
"""Tests for research health summaries."""

import json
from datetime import datetime, timedelta, timezone

from agent_reach.research.health import build_health_report
from agent_reach.research.models import ResearchProfile, SourceItem
from agent_reach.research.runtime import worker_status_path
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store import SQLiteResearchStore
from agent_reach.research.worker import ResearchScheduler, ResearchWorker


class _StubAdapter:
    def __init__(self, source_name: str, available: bool, hint: str):
        self.source_name = source_name
        self._available = available
        self.health_hint = hint

    def is_available(self) -> bool:
        return self._available

    def health_details(self) -> dict[str, str]:
        return {"source": self.source_name, "hint": self.health_hint}


class _NoopWorker(ResearchWorker):
    def __init__(self, store, settings, adapters):
        super().__init__(store=store, settings=settings, adapters=adapters)


def _settings(tmp_path) -> ResearchSettings:
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


def test_build_health_report_surfaces_worker_and_source_degradation(tmp_path):
    settings = _settings(tmp_path)
    store = SQLiteResearchStore(settings.db_path)
    store.initialize()
    profile = ResearchProfile(
        name="Researcher",
        persona_brief="Analytical",
        niche_definition="AI systems",
    )
    store.upsert_profile(profile)
    store.upsert_source_items(
        [
            SourceItem(
                research_profile_id=profile.id,
                source="reddit",
                external_id="abc",
                canonical_url="https://reddit.com/abc",
                author_name="alice",
                published_at=datetime.now(timezone.utc) - timedelta(days=10),
                title="Old signal",
                body_text="Still relevant",
            )
        ]
    )
    status_payload = {
        "worker_name": "research-worker",
        "pid": 123,
        "state": "running",
        "note": "No due jobs.",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=1000)).isoformat(),
        "tick_count": 3,
        "active_profile_id": profile.id,
        "last_result": None,
        "last_error": None,
    }
    status_path = worker_status_path(settings)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status_payload), encoding="utf-8")

    report = build_health_report(
        settings=settings,
        store=store,
        adapters=[
            _StubAdapter("reddit", True, "Requires rdt"),
            _StubAdapter("x", False, "Requires twitter"),
        ],
        profile_id=profile.id,
    )

    assert report["status"] == "degraded"
    assert report["worker"]["stale"] is True
    assert report["worker"]["status"] == "degraded"
    source_map = {item["source"]: item for item in report["sources"]}
    assert source_map["reddit"]["status"] == "degraded"
    assert source_map["x"]["available"] is False
