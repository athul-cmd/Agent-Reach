# -*- coding: utf-8 -*-
"""Tests for research artifact storage helpers."""

from datetime import datetime, timezone
import json
from pathlib import Path

from agent_reach.research.artifacts import (
    build_snapshot_key,
    build_source_artifact_key,
    write_snapshot_artifact,
    write_source_artifact,
)
from agent_reach.research.settings import ResearchSettings


def test_write_source_artifact_uses_profile_source_and_date_layout(tmp_path):
    settings = ResearchSettings(
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
    path = write_source_artifact(
        settings=settings,
        profile_id="profile_123",
        source="reddit",
        query="AI content strategy",
        external_id="post_456",
        payload={"hello": "world"},
        collected_at=datetime(2026, 4, 11, 6, 0, tzinfo=timezone.utc),
    )

    artifact_path = Path(path)
    assert artifact_path.exists()
    assert "profile_123" in artifact_path.parts
    assert "raw" in artifact_path.parts
    assert "reddit" in artifact_path.parts
    assert artifact_path.name.endswith(".json")

    stored = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert stored == {"hello": "world"}


def test_snapshot_key_and_blob_write_use_profile_and_month_layout(tmp_path):
    settings = ResearchSettings(
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
    key = build_snapshot_key(
        profile_id="profile_abc",
        report_id="report_xyz",
        published_at=datetime(2026, 4, 14, 8, 0, tzinfo=timezone.utc),
    )
    path = write_snapshot_artifact(
        settings=settings,
        profile_id="profile_abc",
        report_id="report_xyz",
        payload_text='{"ok":true}',
        published_at=datetime(2026, 4, 14, 8, 0, tzinfo=timezone.utc),
    )

    snapshot_path = Path(path)
    assert snapshot_path.parent.exists()
    assert snapshot_path.name == "report_xyz.nodepad"
    assert "profile_abc" in snapshot_path.parts
    assert "snapshots" in snapshot_path.parts
    assert "2026" in snapshot_path.parts
    assert "04" in snapshot_path.parts
    assert key.endswith("profile_abc/snapshots/2026/04/report_xyz.nodepad")


def test_source_artifact_key_has_expected_layout():
    key = build_source_artifact_key(
        profile_id="profile_123",
        source="reddit",
        query="AI content strategy",
        external_id="post_456",
        collected_at=datetime(2026, 4, 11, 6, 0, tzinfo=timezone.utc),
    )

    assert key == "profile_123/raw/reddit/2026/04/11/ai-content-strategy__post_456.json"
