# -*- coding: utf-8 -*-
"""Operational health summaries for the research system."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from agent_reach.research.adapters.base import SourceAdapter
from agent_reach.research.maintenance import storage_status
from agent_reach.research.models import JobRun, JobStatus, SourceItem
from agent_reach.research.runtime import load_worker_status
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store_protocol import ResearchStore


def build_health_report(
    *,
    settings: ResearchSettings,
    store: ResearchStore,
    adapters: Sequence[SourceAdapter],
    profile_id: str | None,
) -> dict[str, Any]:
    """Build an operator-facing health summary for the API, worker, jobs, and sources."""
    now = datetime.now(timezone.utc)
    worker = _worker_health(settings, now)
    jobs = _job_health(store, profile_id)
    sources = _source_health(store, profile_id, adapters, now)
    overall = _overall_status(worker["status"], jobs["status"], sources)
    return {
        "generated_at": now.isoformat(),
        "status": overall,
        "worker": worker,
        "jobs": jobs,
        "sources": sources,
        "storage": storage_status(settings),
    }


def _worker_health(settings: ResearchSettings, now: datetime) -> dict[str, Any]:
    payload = load_worker_status(settings)
    if payload is None:
        return {
            "status": "degraded",
            "state": "unknown",
            "note": "No worker status file found.",
            "stale": True,
            "last_update_at": None,
        }
    updated_at = _parse_iso(payload.get("updated_at"))
    stale_after = timedelta(seconds=max(60, settings.scheduler_heartbeat_seconds * 2))
    stale = updated_at is None or now - updated_at > stale_after
    state = str(payload.get("state") or "unknown")
    status = "ok"
    if stale or state in {"error", "stopping"}:
        status = "degraded"
    if state == "stopped" and not stale:
        status = "degraded"
    return {
        "status": status,
        "state": state,
        "note": str(payload.get("note") or ""),
        "stale": stale,
        "last_update_at": payload.get("updated_at"),
        "tick_count": int(payload.get("tick_count") or 0),
        "active_profile_id": payload.get("active_profile_id"),
        "last_result": payload.get("last_result"),
        "last_error": payload.get("last_error"),
    }


def _job_health(store: ResearchStore, profile_id: str | None) -> dict[str, Any]:
    if not profile_id:
        return {
            "status": "ok",
            "latest_jobs": [],
            "failed_job_count": 0,
            "pending_job_count": 0,
        }
    jobs = store.list_jobs(profile_id, limit=50)
    latest_by_type: dict[str, JobRun] = {}
    for job in jobs:
        key = job.job_type.value
        if key not in latest_by_type:
            latest_by_type[key] = job
    latest_jobs = []
    failed = 0
    pending = 0
    for job in latest_by_type.values():
        if job.status == JobStatus.FAILED:
            failed += 1
        if job.status == JobStatus.PENDING:
            pending += 1
        latest_jobs.append(
            {
                "job_type": job.job_type.value,
                "status": job.status.value,
                "scheduled_for": job.scheduled_for.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "error_summary": job.error_summary,
            }
        )
    status = "degraded" if failed else "ok"
    return {
        "status": status,
        "latest_jobs": sorted(latest_jobs, key=lambda item: item["job_type"]),
        "failed_job_count": failed,
        "pending_job_count": pending,
    }


def _source_health(
    store: ResearchStore,
    profile_id: str | None,
    adapters: Sequence[SourceAdapter],
    now: datetime,
) -> list[dict[str, Any]]:
    items = store.list_source_items(profile_id, limit=500) if profile_id else []
    latest_by_source: dict[str, SourceItem] = {}
    counts: dict[str, int] = {}
    for item in items:
        counts[item.source] = counts.get(item.source, 0) + 1
        existing = latest_by_source.get(item.source)
        if existing is None or item.published_at > existing.published_at:
            latest_by_source[item.source] = item

    payloads: list[dict[str, Any]] = []
    for adapter in adapters:
        available = adapter.is_available()
        latest_item = latest_by_source.get(adapter.source_name)
        latest_published_at = latest_item.published_at if latest_item else None
        stale = latest_published_at is None or now - latest_published_at > timedelta(days=7)
        status = "ok"
        if not available:
            status = "degraded"
        elif stale and counts.get(adapter.source_name, 0) == 0:
            status = "degraded"
        elif stale:
            status = "degraded"
        payload = adapter.health_details()
        payloads.append(
            {
                "source": adapter.source_name,
                "status": status,
                "available": available,
                "hint": payload.get("hint", ""),
                "item_count": counts.get(adapter.source_name, 0),
                "latest_published_at": latest_published_at.isoformat() if latest_published_at else None,
                "latest_health_status": latest_item.health_status if latest_item else None,
                "stale": stale,
            }
        )
    return payloads


def _overall_status(worker_status: str, job_status: str, sources: Sequence[dict[str, Any]]) -> str:
    if worker_status != "ok" or job_status != "ok":
        return "degraded"
    if any(source.get("status") != "ok" for source in sources):
        return "degraded"
    return "ok"


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
