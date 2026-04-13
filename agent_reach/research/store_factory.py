# -*- coding: utf-8 -*-
"""Factory for selecting the active research persistence backend."""

from __future__ import annotations

from agent_reach.research.postgres_store import PostgresResearchStore
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store import SQLiteResearchStore
from agent_reach.research.store_protocol import ResearchStore


def create_research_store(settings: ResearchSettings) -> ResearchStore:
    """Build the configured research store backend."""
    backend = (settings.db_backend or "supabase").strip().lower()
    if backend in {"postgres", "supabase"}:
        if not settings.db_dsn:
            raise RuntimeError("Postgres/Supabase backend selected but `db_dsn` is empty.")
        return PostgresResearchStore(settings.db_dsn)
    return SQLiteResearchStore(settings.db_path)
