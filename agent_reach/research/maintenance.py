# -*- coding: utf-8 -*-
"""Operational helpers for storage preparation and artifact retention."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from agent_reach.research.blob_store import BlobObject
from agent_reach.research.blob_store_factory import create_blob_store
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store_protocol import ResearchStore

ArtifactKind = Literal["raw", "snapshots", "all"]


def prepare_storage(settings: ResearchSettings, store: ResearchStore) -> dict[str, Any]:
    """Initialize configured local directories and database schema."""
    settings.ensure_dirs()
    store.initialize()
    create_blob_store(settings)
    return {
        "db_backend": settings.db_backend,
        "db_target": settings.db_path if settings.db_backend == "sqlite" else settings.db_dsn,
        "blob_backend": settings.blob_backend,
        "blob_target": settings.blob_root_dir if settings.blob_backend == "local" else settings.blob_bucket,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }


def storage_status(settings: ResearchSettings) -> dict[str, Any]:
    """Return the effective storage configuration for operator inspection."""
    return {
        "db_backend": settings.db_backend,
        "db_path": settings.db_path,
        "db_dsn": settings.db_dsn,
        "blob_backend": settings.blob_backend,
        "blob_root_dir": settings.blob_root_dir,
        "blob_bucket": settings.blob_bucket,
        "blob_prefix": settings.blob_prefix,
        "blob_region": settings.blob_region,
        "blob_endpoint_url": settings.blob_endpoint_url,
        "blob_public_base_url": settings.blob_public_base_url,
        "supabase_url": settings.supabase_url,
    }


def cleanup_artifacts(
    settings: ResearchSettings,
    *,
    kind: ArtifactKind,
    older_than_days: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete stale raw artifacts or snapshot exports from the configured blob store."""
    if older_than_days <= 0:
        raise ValueError("older_than_days must be greater than zero.")

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    store = create_blob_store(settings)
    all_objects = store.list_objects()
    candidates = [
        item
        for item in all_objects
        if _matches_kind(item, kind) and datetime.fromtimestamp(item.updated_at, timezone.utc) < cutoff
    ]
    deleted = 0
    if not dry_run and candidates:
        deleted = store.delete_objects([item.key for item in candidates])
    return {
        "kind": kind,
        "older_than_days": older_than_days,
        "dry_run": dry_run,
        "cutoff": cutoff.isoformat(),
        "candidate_count": len(candidates),
        "deleted_count": 0 if dry_run else deleted,
        "candidates": [_blob_payload(item) for item in candidates[:25]],
    }


def _matches_kind(item: BlobObject, kind: ArtifactKind) -> bool:
    if kind == "all":
        return "/raw/" in item.key or "/snapshots/" in item.key
    marker = f"/{kind}/"
    return marker in item.key


def _blob_payload(item: BlobObject) -> dict[str, Any]:
    return {
        "key": item.key,
        "uri": item.uri,
        "updated_at": datetime.fromtimestamp(item.updated_at, timezone.utc).isoformat(),
        "size_bytes": item.size_bytes,
    }
