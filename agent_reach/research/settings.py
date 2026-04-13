# -*- coding: utf-8 -*-
"""Settings loader for the research subsystem."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Any, Dict

import yaml

from agent_reach.config import Config


@dataclass(slots=True)
class ResearchSettings:
    """Runtime settings for the research system."""

    db_backend: str
    db_path: str
    db_dsn: str
    blob_backend: str
    blob_root_dir: str
    blob_bucket: str
    blob_prefix: str
    raw_artifact_dir: str
    snapshot_dir: str
    runtime_dir: str
    blob_region: str = ""
    blob_endpoint_url: str = ""
    blob_public_base_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    api_access_token: str = ""
    supabase_owner_user_id: str = ""
    settings_encryption_key: str = ""
    timezone: str = "Asia/Kolkata"
    scheduler_heartbeat_seconds: int = 300
    collection_interval_seconds: int = 4 * 60 * 60
    daily_synthesis_hour: int = 6
    weekly_digest_weekday: int = 0
    weekly_digest_hour: int = 8
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    source_result_limit: int = 10

    @classmethod
    def default(cls) -> "ResearchSettings":
        """Create default settings rooted in the Agent Reach config directory."""
        base_dir = Config.CONFIG_DIR
        configured_dsn = os.environ.get("AGENT_REACH_RESEARCH_DB_DSN", "")
        default_backend = "supabase"
        db_backend = os.environ.get("AGENT_REACH_RESEARCH_DB_BACKEND", default_backend)
        supabase_url = os.environ.get(
            "AGENT_REACH_RESEARCH_SUPABASE_URL",
            os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""),
        )
        supabase_service_role_key = os.environ.get(
            "AGENT_REACH_RESEARCH_SUPABASE_SERVICE_ROLE_KEY",
            "",
        )
        blob_bucket = os.environ.get("AGENT_REACH_RESEARCH_BLOB_BUCKET", "")
        default_blob_backend = "supabase" if (
            db_backend == "supabase" and supabase_url and supabase_service_role_key and blob_bucket
        ) else "local"
        return cls(
            db_backend=db_backend,
            db_path=str(base_dir / "research.db"),
            db_dsn=configured_dsn,
            supabase_owner_user_id=os.environ.get("AGENT_REACH_RESEARCH_SUPABASE_OWNER_USER_ID", ""),
            blob_backend=os.environ.get("AGENT_REACH_RESEARCH_BLOB_BACKEND", default_blob_backend),
            blob_root_dir=str(base_dir / "research" / "blobs"),
            blob_bucket=blob_bucket,
            blob_prefix=os.environ.get("AGENT_REACH_RESEARCH_BLOB_PREFIX", "agent-reach/research"),
            blob_region=os.environ.get("AGENT_REACH_RESEARCH_BLOB_REGION", ""),
            blob_endpoint_url=os.environ.get("AGENT_REACH_RESEARCH_BLOB_ENDPOINT_URL", ""),
            blob_public_base_url=os.environ.get("AGENT_REACH_RESEARCH_BLOB_PUBLIC_BASE_URL", ""),
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_service_role_key,
            raw_artifact_dir=str(base_dir / "research" / "raw"),
            snapshot_dir=str(base_dir / "research" / "snapshots"),
            runtime_dir=str(base_dir / "research" / "runtime"),
            api_access_token=os.environ.get("AGENT_REACH_RESEARCH_API_ACCESS_TOKEN", ""),
            settings_encryption_key=os.environ.get("AGENT_REACH_RESEARCH_SETTINGS_ENCRYPTION_KEY", ""),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        )

    @classmethod
    def load(cls, path: Path | None = None) -> "ResearchSettings":
        """Load settings from YAML, falling back to defaults."""
        config_path = path or (Config.CONFIG_DIR / "research_settings.yaml")
        settings = cls.default()
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for key, value in data.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
        if not settings.openai_api_key:
            settings.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        return settings

    def save(self, path: Path | None = None) -> Path:
        """Persist current settings to YAML."""
        config_path = path or (Config.CONFIG_DIR / "research_settings.yaml")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(asdict(self), f, sort_keys=True, allow_unicode=True)
        self.ensure_dirs()
        return config_path

    def ensure_dirs(self) -> None:
        """Create runtime directories if missing."""
        Path(self.raw_artifact_dir).mkdir(parents=True, exist_ok=True)
        Path(self.snapshot_dir).mkdir(parents=True, exist_ok=True)
        Path(self.runtime_dir).mkdir(parents=True, exist_ok=True)
        if self.blob_backend == "local":
            Path(self.blob_root_dir).mkdir(parents=True, exist_ok=True)
        if self.db_backend == "sqlite":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """Return a safe dict representation."""
        data = asdict(self)
        if data.get("openai_api_key"):
            data["openai_api_key"] = f"{data['openai_api_key'][:8]}..."
        if data.get("api_access_token"):
            data["api_access_token"] = f"{data['api_access_token'][:8]}..."
        if data.get("settings_encryption_key"):
            data["settings_encryption_key"] = f"{data['settings_encryption_key'][:8]}..."
        if data.get("supabase_service_role_key"):
            data["supabase_service_role_key"] = f"{data['supabase_service_role_key'][:8]}..."
        return data
