# -*- coding: utf-8 -*-
"""Tests for research blob store backend selection."""

from agent_reach.research.blob_store import LocalBlobStore, S3BlobStore, SupabaseBlobStore
from agent_reach.research.blob_store_factory import create_blob_store
from agent_reach.research.settings import ResearchSettings


def test_blob_store_factory_defaults_to_local():
    settings = ResearchSettings(
        db_backend="sqlite",
        db_path="/tmp/research.db",
        db_dsn="",
        blob_backend="local",
        blob_root_dir="/tmp/blobs",
        blob_bucket="",
        blob_prefix="agent-reach/research",
        raw_artifact_dir="/tmp/raw",
        snapshot_dir="/tmp/snapshots",
        runtime_dir="/tmp/runtime",
    )

    store = create_blob_store(settings)

    assert isinstance(store, LocalBlobStore)


def test_blob_store_factory_builds_s3_store_without_connecting():
    settings = ResearchSettings(
        db_backend="sqlite",
        db_path="/tmp/research.db",
        db_dsn="",
        blob_backend="s3",
        blob_root_dir="/tmp/blobs",
        blob_bucket="research-bucket",
        blob_prefix="agent-reach/research",
        blob_region="us-east-1",
        blob_endpoint_url="https://s3.example.com",
        blob_public_base_url="https://cdn.example.com/research",
        raw_artifact_dir="/tmp/raw",
        snapshot_dir="/tmp/snapshots",
        runtime_dir="/tmp/runtime",
    )

    store = create_blob_store(settings)

    assert isinstance(store, S3BlobStore)
    assert store.bucket == "research-bucket"
    assert store.prefix == "agent-reach/research"


def test_blob_store_factory_builds_supabase_store_without_connecting():
    settings = ResearchSettings(
        db_backend="supabase",
        db_path="/tmp/research.db",
        db_dsn="postgresql://example",
        blob_backend="supabase",
        blob_root_dir="/tmp/blobs",
        blob_bucket="research-artifacts",
        blob_prefix="agent-reach/research",
        raw_artifact_dir="/tmp/raw",
        snapshot_dir="/tmp/snapshots",
        runtime_dir="/tmp/runtime",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role",
        blob_public_base_url="https://example.supabase.co/storage/v1/object/public/research-artifacts",
    )

    store = create_blob_store(settings)

    assert isinstance(store, SupabaseBlobStore)
    assert store.bucket == "research-artifacts"
    assert store.prefix == "agent-reach/research"
