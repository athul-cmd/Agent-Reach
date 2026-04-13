# -*- coding: utf-8 -*-
"""Helpers for resolving encrypted server-side secrets from Supabase-backed Postgres."""

from __future__ import annotations

import base64
import json
from hashlib import sha256
from typing import Any

from agent_reach.research.settings import ResearchSettings


def _load_crypto():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise RuntimeError(
            "Encrypted settings require `cryptography`. Install with `pip install 'agent-reach[crypto]'`."
        ) from exc
    return AESGCM


def _connect(dsn: str):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "Supabase-backed secret resolution requires `psycopg`. Install with `pip install 'agent-reach[postgres]'`."
        ) from exc
    return psycopg.connect(dsn, row_factory=dict_row)


def _derive_key(secret: str) -> bytes:
    return sha256(secret.encode("utf-8")).digest()


def decrypt_server_secret(payload_text: str, secret: str) -> str:
    payload = json.loads(payload_text)
    if payload.get("v") != 1 or payload.get("alg") != "aes-256-gcm":
        raise RuntimeError("Unsupported encrypted secret payload.")
    AESGCM = _load_crypto()
    aesgcm = AESGCM(_derive_key(secret))
    iv = base64.b64decode(payload["iv"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    tag = base64.b64decode(payload["tag"])
    plaintext = aesgcm.decrypt(iv, ciphertext + tag, None)
    return plaintext.decode("utf-8")


def _fetch_settings_row(settings: ResearchSettings) -> dict[str, Any] | None:
    if not settings.db_dsn:
        return None
    with _connect(settings.db_dsn) as conn:
        with conn.cursor() as cur:
            if settings.supabase_owner_user_id:
                cur.execute(
                    """
                    SELECT user_id, openai_api_key_ciphertext, openai_api_key_last4, updated_at
                    FROM research_user_settings
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (settings.supabase_owner_user_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT user_id, openai_api_key_ciphertext, openai_api_key_last4, updated_at
                    FROM research_user_settings
                    WHERE openai_api_key_ciphertext IS NOT NULL
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                )
            return cur.fetchone()


def resolve_openai_api_key(settings: ResearchSettings) -> str:
    """Resolve the effective OpenAI API key from env or encrypted DB settings."""
    if settings.openai_api_key:
        return settings.openai_api_key

    if not settings.settings_encryption_key:
        return ""

    backend = (settings.db_backend or "").strip().lower()
    if backend not in {"postgres", "supabase"}:
        return ""

    row = _fetch_settings_row(settings)
    if not row:
        return ""
    ciphertext = row.get("openai_api_key_ciphertext")
    if not ciphertext:
        return ""
    return decrypt_server_secret(ciphertext, settings.settings_encryption_key)
