# -*- coding: utf-8 -*-
"""Tests for research storage preparation and artifact cleanup."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

from agent_reach.research.artifacts import write_snapshot_artifact, write_source_artifact
from agent_reach.research.maintenance import cleanup_artifacts, prepare_storage
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store import SQLiteResearchStore


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


def test_prepare_storage_initializes_sqlite_and_local_blob_root(tmp_path):
    settings = _settings(tmp_path)
    store = SQLiteResearchStore(settings.db_path)

    summary = prepare_storage(settings, store)

    assert summary["db_backend"] == "sqlite"
    assert Path(settings.db_path).exists()
    assert Path(settings.blob_root_dir).exists()


def test_cleanup_artifacts_dry_run_and_delete_only_old_matching_kind(tmp_path):
    settings = _settings(tmp_path)
    store = SQLiteResearchStore(settings.db_path)
    prepare_storage(settings, store)

    raw_path = Path(
        write_source_artifact(
            settings=settings,
            profile_id="profile_123",
            source="reddit",
            query="AI content strategy",
            external_id="post_1",
            payload={"body": "old raw"},
        )
    )
    snapshot_path = Path(
        write_snapshot_artifact(
            settings=settings,
            profile_id="profile_123",
            report_id="report_1",
            payload_text='{"ok":true}',
        )
    )

    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()
    os.utime(raw_path, (old_timestamp, old_timestamp))

    dry_run = cleanup_artifacts(settings, kind="raw", older_than_days=30, dry_run=True)
    assert dry_run["candidate_count"] == 1
    assert dry_run["deleted_count"] == 0
    assert raw_path.exists()

    deleted = cleanup_artifacts(settings, kind="raw", older_than_days=30, dry_run=False)

    assert deleted["candidate_count"] == 1
    assert deleted["deleted_count"] == 1
    assert not raw_path.exists()
    assert snapshot_path.exists()
