# -*- coding: utf-8 -*-
"""Persistent runtime wrapper for the research scheduler."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import time
from typing import Any

from agent_reach.research.maintenance import prepare_storage
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.store_protocol import ResearchStore
from agent_reach.research.worker import ResearchScheduler, ResearchWorker


def worker_status_path(settings: ResearchSettings) -> Path:
    """Return the canonical status file for the persistent research worker."""
    return Path(settings.runtime_dir) / "worker-status.json"


def load_worker_status(settings: ResearchSettings) -> dict[str, Any] | None:
    """Read the last known worker runtime status if it exists."""
    path = worker_status_path(settings)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class ResearchWorkerService:
    """Long-running process wrapper around the scheduler loop."""

    def __init__(
        self,
        *,
        store: ResearchStore,
        settings: ResearchSettings,
        worker: ResearchWorker,
        scheduler: ResearchScheduler,
        sleep_seconds: int | None = None,
        worker_name: str = "research-worker",
    ):
        self.store = store
        self.settings = settings
        self.worker = worker
        self.scheduler = scheduler
        self.sleep_seconds = max(1, int(sleep_seconds or settings.scheduler_heartbeat_seconds))
        self.worker_name = worker_name
        self.pid = os.getpid()
        self.started_at = datetime.now(timezone.utc)
        self.tick_count = 0
        self.last_result: dict[str, Any] | None = None
        self.last_error: str | None = None
        self.active_profile_id: str | None = None
        self._running = False

    def initialize(self) -> None:
        """Prepare storage and write initial runtime status."""
        prepare_storage(self.settings, self.store)
        self._write_status(state="starting")

    def run_forever(self, profile_id: str | None = None, max_ticks: int = 0) -> None:
        """Run the scheduler loop until stopped or until max_ticks is reached."""
        self._install_signal_handlers()
        self._running = True
        self.active_profile_id = profile_id
        self._write_status(state="running")

        while self._running:
            self.tick_count += 1
            profile_id = profile_id or self._resolve_profile_id()
            if not profile_id:
                self.last_result = None
                self.last_error = None
                self._write_status(state="idle", note="No active research profile.")
                if max_ticks and self.tick_count >= max_ticks:
                    break
                time.sleep(self.sleep_seconds)
                continue

            try:
                self.active_profile_id = profile_id
                result = self.scheduler.tick(profile_id)
                self.last_result = result
                self.last_error = None
                state = "running" if result else "idle"
                note = "Executed due job." if result else "No due jobs."
                self._write_status(state=state, note=note)
            except Exception as exc:
                self.last_error = str(exc)
                self.last_result = None
                self._write_status(state="error", note=str(exc))

            if max_ticks and self.tick_count >= max_ticks:
                break
            if self._running:
                time.sleep(self.sleep_seconds)

        self._running = False
        self._write_status(state="stopped")

    def stop(self) -> None:
        """Request a graceful shutdown."""
        self._running = False

    def _resolve_profile_id(self) -> str | None:
        profile = self.store.get_latest_profile()
        if profile is None:
            return None
        return profile.id

    def _install_signal_handlers(self) -> None:
        for sig in ("SIGINT", "SIGTERM"):
            handler = getattr(signal, sig, None)
            if handler is None:
                continue
            signal.signal(handler, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: object) -> None:
        self.last_error = None
        self._write_status(state="stopping", note=f"Received signal {signum}.")
        self.stop()

    def _write_status(self, *, state: str, note: str = "") -> None:
        path = worker_status_path(self.settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "worker_name": self.worker_name,
            "pid": self.pid,
            "state": state,
            "note": note,
            "started_at": self.started_at.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tick_count": self.tick_count,
            "active_profile_id": self.active_profile_id,
            "sleep_seconds": self.sleep_seconds,
            "last_result": self.last_result,
            "last_error": self.last_error,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
