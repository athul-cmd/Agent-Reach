# -*- coding: utf-8 -*-
"""Base adapter contract for research source collection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from agent_reach.research.models import ResearchProfile, SourceItem
from agent_reach.research.settings import ResearchSettings


class SourceAdapter(ABC):
    """Abstract source adapter."""

    source_name: str = ""
    health_hint: str = ""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the adapter can execute on the current machine."""
        ...

    @abstractmethod
    def collect(
        self,
        profile: ResearchProfile,
        settings: ResearchSettings,
        limit: int,
    ) -> List[SourceItem]:
        """Collect source items for a profile."""
        ...

    def health_details(self) -> dict[str, str]:
        """Return static operator-facing details about this adapter."""
        return {
            "source": self.source_name,
            "hint": self.health_hint or self.source_name,
        }
