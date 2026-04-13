# -*- coding: utf-8 -*-
"""Connectivity and smoke verification helpers for research deployments."""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Any, Sequence

from agent_reach.research.adapters.base import SourceAdapter
from agent_reach.research.blob_store_factory import create_blob_store
from agent_reach.research.models import ResearchProfile
from agent_reach.research.settings import ResearchSettings


def verify_storage(settings: ResearchSettings) -> dict[str, Any]:
    """Run live connectivity checks for the configured DB and blob backends."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": _verify_database(settings),
        "blob_store": _verify_blob_store(settings),
    }


def verify_sources(
    *,
    settings: ResearchSettings,
    profile: ResearchProfile | None,
    adapters: Sequence[SourceAdapter],
    run_collect: bool = False,
    limit: int = 1,
) -> dict[str, Any]:
    """Verify source adapter availability and optional live collection."""
    checks = []
    overall = "ok"
    for adapter in adapters:
        available = adapter.is_available()
        check: dict[str, Any] = {
            "source": adapter.source_name,
            "available": available,
            "hint": adapter.health_details().get("hint", ""),
            "status": "ok" if available else "degraded",
        }
        if run_collect:
            if not available:
                check["status"] = "degraded"
                check["error"] = "Adapter is unavailable on this machine."
            elif profile is None:
                check["status"] = "degraded"
                check["error"] = "No active research profile for live source collection."
            else:
                try:
                    items = adapter.collect(profile, settings, max(1, limit))
                    check["sample_count"] = len(items)
                except Exception as exc:
                    check["status"] = "degraded"
                    check["error"] = str(exc)
        if check["status"] != "ok":
            overall = "degraded"
        checks.append(check)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": overall,
        "run_collect": run_collect,
        "checks": checks,
    }


def verify_all(
    *,
    settings: ResearchSettings,
    profile: ResearchProfile | None,
    adapters: Sequence[SourceAdapter],
    run_source_collect: bool = False,
    source_limit: int = 1,
) -> dict[str, Any]:
    """Run storage and source verification in one operator-facing payload."""
    storage = verify_storage(settings)
    sources = verify_sources(
        settings=settings,
        profile=profile,
        adapters=adapters,
        run_collect=run_source_collect,
        limit=source_limit,
    )
    status = "ok"
    if storage["database"]["status"] != "ok" or storage["blob_store"]["status"] != "ok":
        status = "degraded"
    if sources["status"] != "ok":
        status = "degraded"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "profile_id": profile.id if profile is not None else None,
        "storage": storage,
        "sources": sources,
    }


def _verify_database(settings: ResearchSettings) -> dict[str, Any]:
    backend = (settings.db_backend or "sqlite").strip().lower()
    if backend in {"postgres", "supabase"}:
        result = _verify_postgres(settings)
        result["backend"] = backend
        return result
    return _verify_sqlite(settings)


def _verify_sqlite(settings: ResearchSettings) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(settings.db_path)
        try:
            row = conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return {
            "backend": "sqlite",
            "status": "ok",
            "target": settings.db_path,
            "result": row[0] if row else None,
        }
    except Exception as exc:
        return {
            "backend": "sqlite",
            "status": "degraded",
            "target": settings.db_path,
            "error": str(exc),
        }


def _verify_postgres(settings: ResearchSettings) -> dict[str, Any]:
    if not settings.db_dsn:
        return {
            "backend": "postgres",
            "status": "degraded",
            "target": "",
            "error": "Database backend requires `db_dsn`, but it is empty.",
            "missing_fields": ["db_dsn"],
            "remediation_hint": "Set AGENT_REACH_RESEARCH_DB_DSN to your Supabase/Postgres connection string.",
        }
    try:
        import psycopg
    except ImportError as exc:
        return {
            "backend": "postgres",
            "status": "degraded",
            "target": settings.db_dsn,
            "error": str(exc),
        }
    try:
        with psycopg.connect(settings.db_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
        return {
            "backend": "postgres",
            "status": "ok",
            "target": settings.db_dsn,
            "result": row[0] if row else None,
        }
    except Exception as exc:
        return {
            "backend": "postgres",
            "status": "degraded",
            "target": settings.db_dsn,
            "error": str(exc),
        }


def _verify_blob_store(settings: ResearchSettings) -> dict[str, Any]:
    backend = (settings.blob_backend or "local").strip().lower()
    missing_fields: list[str] = []
    remediation_hint = ""
    if backend == "s3":
        if not settings.blob_bucket:
            missing_fields.append("blob_bucket")
        remediation_hint = "Set AGENT_REACH_RESEARCH_BLOB_BUCKET and related S3 settings."
    elif backend == "supabase":
        if not settings.blob_bucket:
            missing_fields.append("blob_bucket")
        if not settings.supabase_url:
            missing_fields.append("supabase_url")
        if not settings.supabase_service_role_key:
            missing_fields.append("supabase_service_role_key")
        remediation_hint = (
            "Set AGENT_REACH_RESEARCH_BLOB_BUCKET, "
            "AGENT_REACH_RESEARCH_SUPABASE_URL, and "
            "AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY."
        )
    if missing_fields:
        return {
            "backend": backend,
            "status": "degraded",
            "target": settings.blob_root_dir if backend == "local" else settings.blob_bucket,
            "error": f"{backend} blob backend is missing required settings.",
            "missing_fields": missing_fields,
            "remediation_hint": remediation_hint,
        }
    try:
        store = create_blob_store(settings)
        key = "_healthchecks/verify.txt"
        uri = store.put_text(
            key,
            f"verified at {datetime.now(timezone.utc).isoformat()}",
            content_type="text/plain; charset=utf-8",
        )
        deleted = store.delete_objects([key])
        return {
            "backend": backend,
            "status": "ok",
            "target": settings.blob_root_dir if backend == "local" else settings.blob_bucket,
            "probe_uri": uri,
            "deleted_count": deleted,
        }
    except Exception as exc:
        return {
            "backend": backend,
            "status": "degraded",
            "target": settings.blob_root_dir if backend == "local" else settings.blob_bucket,
            "error": str(exc),
            "remediation_hint": remediation_hint or None,
        }
