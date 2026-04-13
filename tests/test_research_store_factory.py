# -*- coding: utf-8 -*-
"""Tests for research store backend selection."""

from agent_reach.research.postgres_store import PostgresResearchStore
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store import SQLiteResearchStore
from agent_reach.research.store_factory import create_research_store


def test_store_factory_defaults_to_sqlite():
    settings = ResearchSettings(
        db_backend="sqlite",
        db_path="/tmp/research.db",
        db_dsn="",
        blob_backend="local",
        blob_root_dir="/tmp/blobs",
        blob_bucket="",
        blob_prefix="agent-reach/research",
        raw_artifact_dir="/tmp/raw",
        snapshot_dir="/tmp/snapshots",
        runtime_dir="/tmp/runtime",
    )

    store = create_research_store(settings)

    assert isinstance(store, SQLiteResearchStore)


def test_store_factory_builds_postgres_store_without_connecting():
    settings = ResearchSettings(
        db_backend="postgres",
        db_path="/tmp/research.db",
        db_dsn="postgresql://user:pass@localhost:5432/research",
        blob_backend="local",
        blob_root_dir="/tmp/blobs",
        blob_bucket="",
        blob_prefix="agent-reach/research",
        raw_artifact_dir="/tmp/raw",
        snapshot_dir="/tmp/snapshots",
        runtime_dir="/tmp/runtime",
    )

    store = create_research_store(settings)

    assert isinstance(store, PostgresResearchStore)
    assert store.dsn == settings.db_dsn
