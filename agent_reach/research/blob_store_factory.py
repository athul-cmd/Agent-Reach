# -*- coding: utf-8 -*-
"""Factory for selecting the active blob storage backend."""

from __future__ import annotations

from agent_reach.research.blob_store import LocalBlobStore, S3BlobStore, SupabaseBlobStore
from agent_reach.research.settings import ResearchSettings


def create_blob_store(settings: ResearchSettings):
    """Build the configured blob store backend."""
    backend = (settings.blob_backend or "local").strip().lower()
    if backend == "supabase":
        if not settings.blob_bucket:
            raise RuntimeError("Supabase blob backend selected but `blob_bucket` is empty.")
        if not settings.supabase_url:
            raise RuntimeError("Supabase blob backend selected but `supabase_url` is empty.")
        if not settings.supabase_service_role_key:
            raise RuntimeError("Supabase blob backend selected but `supabase_service_role_key` is empty.")
        return SupabaseBlobStore(
            base_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.blob_bucket,
            prefix=settings.blob_prefix,
            public_base_url=settings.blob_public_base_url,
        )
    if backend == "s3":
        if not settings.blob_bucket:
            raise RuntimeError("S3 blob backend selected but `blob_bucket` is empty.")
        return S3BlobStore(
            bucket=settings.blob_bucket,
            prefix=settings.blob_prefix,
            region=settings.blob_region,
            endpoint_url=settings.blob_endpoint_url,
            public_base_url=settings.blob_public_base_url,
        )
    return LocalBlobStore(settings.blob_root_dir)
