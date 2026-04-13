# -*- coding: utf-8 -*-
"""Blob storage backends for research artifacts and exports."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import quote
from typing import List

import requests


@dataclass(slots=True)
class BlobObject:
    """Metadata for one stored blob object."""

    key: str
    uri: str
    updated_at: float
    size_bytes: int


class LocalBlobStore:
    """Filesystem-backed blob store used for local development."""

    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir).resolve()

    def _path_for_key(self, key: str) -> Path:
        return self.root_dir / key

    def _key_for_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.root_dir).as_posix()

    def put_bytes(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        del content_type
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path.resolve())

    def put_json(self, key: str, payload: object) -> str:
        return self.put_bytes(
            key,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def put_text(self, key: str, text: str, content_type: str = "text/plain; charset=utf-8") -> str:
        return self.put_bytes(key, text.encode("utf-8"), content_type=content_type)

    def list_objects(self, prefix: str = "") -> List[BlobObject]:
        base = self._path_for_key(prefix).resolve() if prefix else self.root_dir.resolve()
        if not base.exists():
            return []
        pattern = "**/*" if base.is_dir() else base.name
        candidates = base.rglob("*") if base.is_dir() else [base]
        del pattern
        objects: List[BlobObject] = []
        for path in candidates:
            if not path.is_file():
                continue
            stat = path.stat()
            key = self._key_for_path(path)
            objects.append(
                BlobObject(
                    key=key,
                    uri=str(path.resolve()),
                    updated_at=stat.st_mtime,
                    size_bytes=stat.st_size,
                )
            )
        return sorted(objects, key=lambda item: item.updated_at)

    def delete_objects(self, keys: List[str]) -> int:
        deleted = 0
        for key in keys:
            path = self._path_for_key(key)
            if path.exists() and path.is_file():
                path.unlink()
                deleted += 1
        return deleted


class S3BlobStore:
    """S3-compatible blob store."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region: str = "",
        endpoint_url: str = "",
        public_base_url: str = "",
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region
        self.endpoint_url = endpoint_url or None
        self.public_base_url = public_base_url.rstrip("/")

    def _client(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "S3 blob backend requires `boto3`. Install with `pip install 'agent-reach[s3]'`."
            ) from exc
        kwargs = {}
        if self.region:
            kwargs["region_name"] = self.region
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return boto3.client("s3", **kwargs)

    def _full_key(self, key: str) -> str:
        compact = key.lstrip("/")
        if self.prefix:
            return f"{self.prefix}/{compact}"
        return compact

    def _uri_for(self, key: str) -> str:
        full_key = self._full_key(key)
        if self.public_base_url:
            return f"{self.public_base_url}/{full_key}"
        return f"s3://{self.bucket}/{full_key}"

    def put_bytes(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        full_key = self._full_key(key)
        self._client().put_object(
            Bucket=self.bucket,
            Key=full_key,
            Body=content,
            ContentType=content_type,
        )
        return self._uri_for(key)

    def put_json(self, key: str, payload: object) -> str:
        return self.put_bytes(
            key,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def put_text(self, key: str, text: str, content_type: str = "text/plain; charset=utf-8") -> str:
        return self.put_bytes(key, text.encode("utf-8"), content_type=content_type)

    def list_objects(self, prefix: str = "") -> List[BlobObject]:
        client = self._client()
        full_prefix = self._full_key(prefix)
        paginator = client.get_paginator("list_objects_v2")
        objects: List[BlobObject] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for item in page.get("Contents", []):
                full_key = item["Key"]
                relative_key = full_key
                if self.prefix and full_key.startswith(f"{self.prefix}/"):
                    relative_key = full_key[len(self.prefix) + 1 :]
                objects.append(
                    BlobObject(
                        key=relative_key,
                        uri=self._uri_for(relative_key),
                        updated_at=item["LastModified"].timestamp(),
                        size_bytes=int(item.get("Size", 0)),
                    )
                )
        return sorted(objects, key=lambda item: item.updated_at)

    def delete_objects(self, keys: List[str]) -> int:
        if not keys:
            return 0
        client = self._client()
        deleted = 0
        chunk_size = 1000
        for index in range(0, len(keys), chunk_size):
            chunk = keys[index : index + chunk_size]
            response = client.delete_objects(
                Bucket=self.bucket,
                Delete={
                    "Objects": [{"Key": self._full_key(key)} for key in chunk],
                    "Quiet": True,
                },
            )
            deleted += len(response.get("Deleted", []))
        return deleted


class SupabaseBlobStore:
    """Supabase Storage-backed blob store."""

    def __init__(
        self,
        base_url: str,
        service_role_key: str,
        bucket: str,
        prefix: str = "",
        public_base_url: str = "",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.service_role_key = service_role_key
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.public_base_url = public_base_url.rstrip("/")
        self.timeout = timeout

    def _full_key(self, key: str) -> str:
        compact = key.lstrip("/")
        if self.prefix:
            return f"{self.prefix}/{compact}"
        return compact

    def _uri_for(self, key: str) -> str:
        full_key = self._full_key(key)
        if self.public_base_url:
            return f"{self.public_base_url}/{full_key}"
        return f"supabase://{self.bucket}/{full_key}"

    def _headers(self, *, content_type: str | None = None, upsert: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }
        if content_type:
            headers["Content-Type"] = content_type
        if upsert:
            headers["x-upsert"] = "true"
        return headers

    def put_bytes(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        full_key = self._full_key(key)
        encoded_key = quote(full_key, safe="/._-")
        response = requests.post(
            f"{self.base_url}/storage/v1/object/{self.bucket}/{encoded_key}",
            headers=self._headers(content_type=content_type, upsert=True),
            data=content,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self._uri_for(key)

    def put_json(self, key: str, payload: object) -> str:
        return self.put_bytes(
            key,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def put_text(self, key: str, text: str, content_type: str = "text/plain; charset=utf-8") -> str:
        return self.put_bytes(key, text.encode("utf-8"), content_type=content_type)

    def list_objects(self, prefix: str = "") -> List[BlobObject]:
        request_prefix = self._full_key(prefix) if prefix else self.prefix
        offset = 0
        limit = 1000
        objects: List[BlobObject] = []
        while True:
            response = requests.post(
                f"{self.base_url}/storage/v1/object/list/{self.bucket}",
                headers=self._headers(content_type="application/json"),
                json={
                    "prefix": request_prefix,
                    "limit": limit,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            items = response.json()
            if not isinstance(items, list) or not items:
                break
            for item in items:
                name = str(item.get("name") or "")
                if not name:
                    continue
                full_key = f"{request_prefix}/{name}".strip("/") if request_prefix else name
                relative_key = full_key
                if self.prefix and full_key.startswith(f"{self.prefix}/"):
                    relative_key = full_key[len(self.prefix) + 1 :]
                metadata = item.get("metadata") or {}
                updated_at = item.get("updated_at") or item.get("created_at") or ""
                timestamp = 0.0
                if updated_at:
                    try:
                        from datetime import datetime

                        timestamp = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00")).timestamp()
                    except Exception:
                        timestamp = 0.0
                objects.append(
                    BlobObject(
                        key=relative_key,
                        uri=self._uri_for(relative_key),
                        updated_at=timestamp,
                        size_bytes=int(metadata.get("size") or 0),
                    )
                )
            if len(items) < limit:
                break
            offset += limit
        return sorted(objects, key=lambda item: item.updated_at)

    def delete_objects(self, keys: List[str]) -> int:
        deleted = 0
        for key in keys:
            full_key = self._full_key(key)
            encoded_key = quote(full_key, safe="/._-")
            response = requests.delete(
                f"{self.base_url}/storage/v1/object/{self.bucket}/{encoded_key}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            if response.status_code in (200, 204):
                deleted += 1
                continue
            response.raise_for_status()
        return deleted
