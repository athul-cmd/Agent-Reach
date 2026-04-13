# -*- coding: utf-8 -*-
"""Shared serialization helpers for research persistence backends."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any


def iso_datetime(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.fromisoformat(value)


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    return json.loads(value)
