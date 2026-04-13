# -*- coding: utf-8 -*-
"""Tests for deployment verification helpers."""

from agent_reach.research.models import ResearchProfile, SourceItem
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.verification import verify_all, verify_sources, verify_storage


class _StubAdapter:
    def __init__(self, source_name: str, available: bool = True, should_fail: bool = False):
        self.source_name = source_name
        self.health_hint = f"hint for {source_name}"
        self._available = available
        self._should_fail = should_fail

    def is_available(self) -> bool:
        return self._available

    def health_details(self) -> dict[str, str]:
        return {"source": self.source_name, "hint": self.health_hint}

    def collect(self, profile: ResearchProfile, settings: ResearchSettings, limit: int):
        del settings
        if self._should_fail:
            raise RuntimeError("boom")
        return [
            SourceItem(
                research_profile_id=profile.id,
                source=self.source_name,
                external_id=f"{self.source_name}-1",
                canonical_url=f"https://example.com/{self.source_name}",
                author_name="author",
                published_at=profile.updated_at,
                title=f"{self.source_name} item",
                body_text="body",
            )
        ][:limit]


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


def test_verify_storage_succeeds_for_local_sqlite_and_blob(tmp_path):
    settings = _settings(tmp_path)

    payload = verify_storage(settings)

    assert payload["database"]["status"] == "ok"
    assert payload["blob_store"]["status"] == "ok"
    assert payload["blob_store"]["deleted_count"] == 1


def test_verify_sources_reports_live_collect_results(tmp_path):
    settings = _settings(tmp_path)
    profile = ResearchProfile(
        name="Researcher",
        persona_brief="Operator-led",
        niche_definition="AI systems",
    )

    payload = verify_sources(
        settings=settings,
        profile=profile,
        adapters=[_StubAdapter("web"), _StubAdapter("x", should_fail=True)],
        run_collect=True,
        limit=1,
    )

    checks = {item["source"]: item for item in payload["checks"]}
    assert payload["status"] == "degraded"
    assert checks["web"]["sample_count"] == 1
    assert checks["x"]["status"] == "degraded"
    assert checks["x"]["error"] == "boom"


def test_verify_all_combines_storage_and_sources(tmp_path):
    settings = _settings(tmp_path)
    profile = ResearchProfile(
        name="Researcher",
        persona_brief="Operator-led",
        niche_definition="AI systems",
    )

    payload = verify_all(
        settings=settings,
        profile=profile,
        adapters=[_StubAdapter("reddit", available=False)],
        run_source_collect=False,
    )

    assert payload["storage"]["database"]["status"] == "ok"
    assert payload["sources"]["status"] == "degraded"
    assert payload["status"] == "degraded"


def test_verify_storage_reports_missing_supabase_blob_configuration(tmp_path):
    settings = ResearchSettings(
        db_backend="supabase",
        db_path=str(tmp_path / "research.db"),
        db_dsn="postgresql://example",
        blob_backend="supabase",
        blob_root_dir=str(tmp_path / "blobs"),
        blob_bucket="",
        blob_prefix="agent-reach/research",
        raw_artifact_dir=str(tmp_path / "raw"),
        snapshot_dir=str(tmp_path / "snapshots"),
        runtime_dir=str(tmp_path / "runtime"),
        supabase_url="",
        supabase_service_role_key="",
    )

    payload = verify_storage(settings)

    assert payload["blob_store"]["status"] == "degraded"
    assert payload["blob_store"]["missing_fields"] == [
        "blob_bucket",
        "supabase_url",
        "supabase_service_role_key",
    ]


def test_verify_storage_reports_missing_postgres_dsn(tmp_path):
    settings = ResearchSettings(
        db_backend="supabase",
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

    payload = verify_storage(settings)

    assert payload["database"]["status"] == "degraded"
    assert payload["database"]["missing_fields"] == ["db_dsn"]
