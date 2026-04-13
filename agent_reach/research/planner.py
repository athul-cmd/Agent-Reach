# -*- coding: utf-8 -*-
"""Deterministic query planning for hosted refresh pipelines."""

from __future__ import annotations

from typing import Any, Dict, List

from agent_reach.research.models import ResearchProfile


def build_refresh_queries(profile: ResearchProfile, max_queries: int = 4) -> List[str]:
    """Build a stable topic query set from the active profile."""
    seeds: List[str] = []
    seeds.extend(topic.strip() for topic in profile.must_track_topics if topic.strip())
    if profile.niche_definition.strip():
        seeds.append(profile.niche_definition.strip())
    if profile.target_audience.strip() and profile.niche_definition.strip():
        seeds.append(f"{profile.niche_definition.strip()} for {profile.target_audience.strip()}")
    if profile.persona_brief.strip() and profile.niche_definition.strip():
        seeds.append(f"{profile.persona_brief.strip()} {profile.niche_definition.strip()}")
    if profile.desired_formats:
        joined_formats = ", ".join(item.strip() for item in profile.desired_formats if item.strip())
        if joined_formats:
            seeds.append(f"{profile.niche_definition.strip()} {joined_formats}".strip())

    deduped: List[str] = []
    seen: set[str] = set()
    for query in seeds:
        compact = " ".join(query.split())
        if not compact:
            continue
        lowered = compact.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(compact)

    return deduped[:max_queries] or ["content strategy"]


def build_query_snapshot(profile: ResearchProfile, max_queries: int = 4) -> Dict[str, Any]:
    """Return a reproducible query planning payload for refresh requests."""
    queries = build_refresh_queries(profile, max_queries=max_queries)
    return {
        "queries": queries,
        "inputs": {
            "must_track_topics": list(profile.must_track_topics),
            "niche_definition": profile.niche_definition,
            "target_audience": profile.target_audience,
            "persona_brief": profile.persona_brief,
            "desired_formats": list(profile.desired_formats),
        },
    }
