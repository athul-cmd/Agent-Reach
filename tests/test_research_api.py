# -*- coding: utf-8 -*-
"""Tests for the research API dispatcher."""

import json

from agent_reach.research.api import ResearchAPI
from agent_reach.research.models import IdeaCard, ResearchProfile
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store import SQLiteResearchStore
from agent_reach.research.worker import ResearchScheduler, ResearchWorker


class _DummyWorker(ResearchWorker):
    def __init__(self, store, settings):
        super().__init__(store=store, settings=settings, adapters=[])

    def run_full_cycle(self, profile_id: str) -> dict:
        return {"profile_id": profile_id, "mode": "full"}

    def run_job(self, job_type, profile_id: str) -> dict:
        return {"profile_id": profile_id, "job_type": job_type.value}


def _build_api(tmp_path) -> ResearchAPI:
    settings = ResearchSettings.default()
    settings.db_path = str(tmp_path / "research.db")
    store = SQLiteResearchStore(settings.db_path)
    worker = _DummyWorker(store=store, settings=settings)
    scheduler = ResearchScheduler(store=store, settings=settings, worker=worker)
    worker.initialize()
    return ResearchAPI(
        store=store,
        worker=worker,
        scheduler=scheduler,
        api_access_token=settings.api_access_token,
    )


def test_dashboard_bootstraps_without_profile(tmp_path):
    api = _build_api(tmp_path)

    status, payload = api.dispatch("GET", "/api/dashboard", b"")

    assert status == 200
    assert payload["system_health"]["status"] in {"ok", "degraded"}
    assert payload["profile"] is None
    assert payload["ideas"] == []
    assert payload["metrics"]["idea_count"] == 0


def test_profile_creation_and_manual_run_dispatch(tmp_path):
    api = _build_api(tmp_path)

    status, payload = api.dispatch(
        "POST",
        "/api/profile",
        json.dumps(
            {
                "name": "Founder Voice",
                "persona_brief": "Direct and analytical",
                "niche_definition": "AI product strategy",
                "target_audience": "operators",
                "must_track_topics": ["AI products", "content systems"],
                "desired_formats": ["linkedin"],
            }
        ).encode("utf-8"),
    )
    assert status == 200
    profile_id = payload["profile"]["id"]

    run_status, run_payload = api.dispatch(
        "POST",
        "/api/runs/manual",
        json.dumps({"profile_id": profile_id, "job": "all"}).encode("utf-8"),
    )

    assert run_status == 200
    assert run_payload["job"] == "all"
    assert run_payload["result"]["mode"] == "full"


def test_idea_save_and_feedback_routes(tmp_path):
    api = _build_api(tmp_path)
    profile = ResearchProfile(
        name="Researcher",
        persona_brief="Operator-led",
        niche_definition="AI content strategy",
    )
    api.store.upsert_profile(profile)
    idea = IdeaCard(
        research_profile_id=profile.id,
        topic_cluster_id="cluster_123",
        headline="A strong angle",
        hook="Public signals are converging.",
        why_now="More creator repetition across sources.",
        outline_md="- First point\n- Second point",
        evidence_item_ids=[],
        final_score=0.8,
    )
    api.store.upsert_idea_cards([idea])

    save_status, save_payload = api.dispatch(
        "POST",
        f"/api/ideas/{idea.id}/save",
        json.dumps({"profile_id": profile.id}).encode("utf-8"),
    )
    feedback_status, feedback_payload = api.dispatch(
        "POST",
        f"/api/ideas/{idea.id}/feedback",
        json.dumps({"profile_id": profile.id, "note": "Use a more contrarian hook"}).encode("utf-8"),
    )

    saved = api.store.list_idea_cards(profile.id, status="saved")
    feedback_events = api.store.list_feedback(profile.id)

    assert save_status == 200
    assert save_payload["status"] == "saved"
    assert feedback_status == 200
    assert feedback_payload["event"] == "feedback"
    assert len(saved) == 1
    assert len(feedback_events) == 2


def test_api_access_token_blocks_unauthorized_requests(tmp_path):
    api = _build_api(tmp_path)
    api.api_access_token = "shared-secret"

    denied_status, denied_payload = api.dispatch("GET", "/api/dashboard", b"")
    allowed_status, allowed_payload = api.dispatch(
        "GET",
        "/api/dashboard",
        b"",
        headers={"X-Research-Api-Token": "shared-secret"},
    )

    assert denied_status == 401
    assert denied_payload["error"] == "Unauthorized."
    assert allowed_status == 200
    assert allowed_payload["profile"] is None


def test_system_health_route_returns_health_payload(tmp_path):
    api = _build_api(tmp_path)

    status, payload = api.dispatch("GET", "/api/system/health", b"")

    assert status == 200
    assert "health" in payload
    assert "worker" in payload["health"]
    assert "sources" in payload["health"]


def test_system_verify_route_returns_storage_payload(tmp_path):
    api = _build_api(tmp_path)

    status, payload = api.dispatch(
        "POST",
        "/api/system/verify",
        json.dumps({"mode": "storage"}).encode("utf-8"),
    )

    assert status == 200
    assert "verification" in payload
    assert "database" in payload["verification"]
