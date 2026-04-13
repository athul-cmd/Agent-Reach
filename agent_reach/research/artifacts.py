# -*- coding: utf-8 -*-
"""Artifact keying and blob-backed storage helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from agent_reach.research.blob_store_factory import create_blob_store
from agent_reach.research.settings import ResearchSettings


def _slug(value: str, fallback: str = "artifact") -> str:
    compact = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return compact[:80] or fallback


def _safe_identifier(value: str, fallback: str = "item") -> str:
    compact = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    compact = compact.strip("._-")
    return compact[:120] or fallback


def build_source_artifact_key(
    profile_id: str,
    source: str,
    query: str,
    external_id: str,
    collected_at: datetime | None = None,
) -> str:
    """Return the canonical blob key for a collected source payload."""
    collected_at = collected_at or datetime.now(timezone.utc)
    return "/".join(
        [
            profile_id,
            "raw",
            _slug(source, "source"),
            collected_at.strftime("%Y"),
            collected_at.strftime("%m"),
            collected_at.strftime("%d"),
            f"{_slug(query, 'query')}__{_safe_identifier(external_id)}.json",
        ]
    )


def build_snapshot_key(
    profile_id: str,
    report_id: str,
    published_at: datetime | None = None,
) -> str:
    """Return the canonical blob key for a Nodepad snapshot export."""
    published_at = published_at or datetime.now(timezone.utc)
    return "/".join(
        [
            profile_id,
            "snapshots",
            published_at.strftime("%Y"),
            published_at.strftime("%m"),
            f"{_safe_identifier(report_id, 'report')}.nodepad",
        ]
    )


def write_source_artifact(
    settings: ResearchSettings,
    profile_id: str,
    source: str,
    query: str,
    external_id: str,
    payload: Any,
    collected_at: datetime | None = None,
) -> str:
    """Persist one normalized raw source payload through the active blob store."""
    key = build_source_artifact_key(
        profile_id=profile_id,
        source=source,
        query=query,
        external_id=external_id,
        collected_at=collected_at,
    )
    return create_blob_store(settings).put_json(key, payload)


def write_snapshot_artifact(
    settings: ResearchSettings,
    profile_id: str,
    report_id: str,
    payload_text: str,
    published_at: datetime | None = None,
) -> str:
    """Persist one Nodepad snapshot payload through the active blob store."""
    key = build_snapshot_key(
        profile_id=profile_id,
        report_id=report_id,
        published_at=published_at,
    )
    return create_blob_store(settings).put_text(
        key,
        payload_text,
        content_type="application/json; charset=utf-8",
    )
