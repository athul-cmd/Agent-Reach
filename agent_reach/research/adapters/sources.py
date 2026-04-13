# -*- coding: utf-8 -*-
"""Best-effort source adapters built on top of existing upstream tools."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
import subprocess
from typing import Any, List

from agent_reach.research.artifacts import write_source_artifact
from agent_reach.research.adapters.base import SourceAdapter
from agent_reach.research.models import ResearchProfile, SourceItem
from agent_reach.research.settings import ResearchSettings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_load_json_blob(blob: str) -> Any:
    blob = blob.strip()
    if not blob:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        start_obj = blob.find("{")
        end_obj = blob.rfind("}")
        if start_obj != -1 and end_obj > start_obj:
            try:
                return json.loads(blob[start_obj : end_obj + 1])
            except json.JSONDecodeError:
                pass
        start_arr = blob.find("[")
        end_arr = blob.rfind("]")
        if start_arr != -1 and end_arr > start_arr:
            try:
                return json.loads(blob[start_arr : end_arr + 1])
            except json.JSONDecodeError:
                pass
    return None


def _profile_queries(profile: ResearchProfile, max_queries: int = 3) -> List[str]:
    queries = []
    for topic in profile.must_track_topics:
        topic = topic.strip()
        if topic:
            queries.append(topic)
    if profile.niche_definition.strip():
        queries.append(profile.niche_definition.strip())
    if profile.persona_brief.strip():
        queries.append(profile.persona_brief.strip())

    deduped = []
    seen = set()
    for query in queries:
        compact = " ".join(query.split())
        if compact.lower() not in seen:
            seen.add(compact.lower())
            deduped.append(compact)
    return deduped[:max_queries] or ["content strategy"]


def _run_command(command: List[str]) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
    )
    output = (result.stdout or "").strip()
    if result.returncode != 0:
        raise RuntimeError((result.stderr or output or "unknown error").strip())
    return output


def _flatten_exa_results(payload: Any) -> List[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _artifact_path(
    settings: ResearchSettings,
    profile: ResearchProfile,
    source: str,
    query: str,
    external_id: str,
    raw_payload: Any,
) -> str:
    return write_source_artifact(
        settings=settings,
        profile_id=profile.id,
        source=source,
        query=query,
        external_id=external_id,
        payload=raw_payload,
        collected_at=_utc_now(),
    )


class WebExaAdapter(SourceAdapter):
    """Collect web search results through Exa via mcporter."""

    source_name = "web"
    health_hint = "Requires `mcporter` with Exa access configured."

    def is_available(self) -> bool:
        return shutil.which("mcporter") is not None

    def collect(
        self,
        profile: ResearchProfile,
        settings: ResearchSettings,
        limit: int,
    ) -> List[SourceItem]:
        items: List[SourceItem] = []
        if not self.is_available():
            return items

        for query in _profile_queries(profile):
            tool_call = f'exa.web_search_exa(query: "{query}", numResults: {limit})'
            try:
                output = _run_command(["mcporter", "call", tool_call])
            except Exception:
                continue
            payload = _safe_load_json_blob(output)
            for result in _flatten_exa_results(payload):
                url = str(
                    result.get("url")
                    or result.get("link")
                    or result.get("id")
                    or ""
                ).strip()
                title = str(result.get("title") or result.get("name") or url).strip()
                summary = str(
                    result.get("text")
                    or result.get("summary")
                    or result.get("snippet")
                    or ""
                ).strip()
                if not url:
                    continue
                published_at = _utc_now()
                items.append(
                    SourceItem(
                        research_profile_id=profile.id,
                        source=self.source_name,
                        external_id=url,
                        canonical_url=url,
                        author_name=str(result.get("author") or result.get("siteName") or "web"),
                        published_at=published_at,
                        title=title[:300],
                        body_text=summary[:4000],
                        engagement={},
                        raw_blob_url=_artifact_path(
                            settings=settings,
                            profile=profile,
                            source=self.source_name,
                            query=query,
                            external_id=url,
                            raw_payload={"query": query, "result": result},
                        ),
                        source_query=query,
                    )
                )
        return items


class RedditAdapter(SourceAdapter):
    """Collect Reddit search results via rdt-cli."""

    source_name = "reddit"
    health_hint = "Requires `rdt` CLI for Reddit collection."

    def is_available(self) -> bool:
        return shutil.which("rdt") is not None

    def collect(
        self,
        profile: ResearchProfile,
        settings: ResearchSettings,
        limit: int,
    ) -> List[SourceItem]:
        items: List[SourceItem] = []
        if not self.is_available():
            return items

        for query in _profile_queries(profile):
            try:
                output = _run_command(["rdt", "search", query, "--limit", str(limit), "--json"])
            except Exception:
                continue
            payload = _safe_load_json_blob(output)
            if not isinstance(payload, list):
                continue
            for result in payload:
                if not isinstance(result, dict):
                    continue
                url = str(result.get("url") or result.get("permalink") or "").strip()
                external_id = str(result.get("id") or url or "").strip()
                title = str(result.get("title") or external_id).strip()
                body = str(result.get("text") or result.get("body") or result.get("content") or "")
                subreddit = str(result.get("subreddit") or "reddit")
                if not external_id:
                    continue
                items.append(
                    SourceItem(
                        research_profile_id=profile.id,
                        source=self.source_name,
                        external_id=external_id,
                        canonical_url=url or f"https://reddit.com/{external_id}",
                        author_name=str(result.get("author") or subreddit),
                        published_at=_utc_now(),
                        title=title[:300],
                        body_text=body[:4000],
                        engagement={
                            "score": result.get("score", 0),
                            "comments": result.get("num_comments", result.get("comments", 0)),
                        },
                        raw_blob_url=_artifact_path(
                            settings=settings,
                            profile=profile,
                            source=self.source_name,
                            query=query,
                            external_id=external_id,
                            raw_payload={"query": query, "result": result},
                        ),
                        source_query=query,
                    )
                )
        return items


class YouTubeAdapter(SourceAdapter):
    """Collect YouTube search results via yt-dlp."""

    source_name = "youtube"
    health_hint = "Requires `yt-dlp` for YouTube metadata and transcript access."

    def is_available(self) -> bool:
        return shutil.which("yt-dlp") is not None

    def collect(
        self,
        profile: ResearchProfile,
        settings: ResearchSettings,
        limit: int,
    ) -> List[SourceItem]:
        items: List[SourceItem] = []
        if not self.is_available():
            return items

        for query in _profile_queries(profile):
            search_target = f"ytsearch{limit}:{query}"
            try:
                output = _run_command(["yt-dlp", "--dump-json", search_target])
            except Exception:
                continue
            for line in output.splitlines():
                try:
                    result = json.loads(line)
                except json.JSONDecodeError:
                    continue
                video_id = str(result.get("id") or "").strip()
                if not video_id:
                    continue
                url = str(result.get("webpage_url") or f"https://youtube.com/watch?v={video_id}")
                title = str(result.get("title") or video_id).strip()
                description = str(result.get("description") or "")
                uploader = str(result.get("channel") or result.get("uploader") or "youtube")
                items.append(
                    SourceItem(
                        research_profile_id=profile.id,
                        source=self.source_name,
                        external_id=video_id,
                        canonical_url=url,
                        author_name=uploader,
                        published_at=_utc_now(),
                        title=title[:300],
                        body_text=description[:4000],
                        engagement={
                            "views": result.get("view_count", 0),
                            "comments": result.get("comment_count", 0),
                            "likes": result.get("like_count", 0),
                        },
                        raw_blob_url=_artifact_path(
                            settings=settings,
                            profile=profile,
                            source=self.source_name,
                            query=query,
                            external_id=video_id,
                            raw_payload={"query": query, "result": result},
                        ),
                        source_query=query,
                    )
                )
        return items


class XAdapter(SourceAdapter):
    """Collect X search results via twitter-cli."""

    source_name = "x"
    health_hint = "Requires `twitter` CLI or compatible X/Twitter access."

    def is_available(self) -> bool:
        return shutil.which("twitter") is not None

    def collect(
        self,
        profile: ResearchProfile,
        settings: ResearchSettings,
        limit: int,
    ) -> List[SourceItem]:
        items: List[SourceItem] = []
        if not self.is_available():
            return items

        for query in _profile_queries(profile):
            try:
                output = _run_command(["twitter", "search", query, "-n", str(limit), "--json"])
            except Exception:
                continue
            payload = _safe_load_json_blob(output)
            if isinstance(payload, dict):
                payload = payload.get("tweets") or payload.get("results") or []
            if not isinstance(payload, list):
                continue
            for result in payload:
                if not isinstance(result, dict):
                    continue
                external_id = str(result.get("id") or result.get("rest_id") or "").strip()
                if not external_id:
                    continue
                text = str(result.get("text") or result.get("full_text") or "")
                url = str(result.get("url") or "").strip()
                if not url:
                    username = str(
                        result.get("username")
                        or result.get("screen_name")
                        or result.get("author", {}).get("screen_name", "")
                    ).strip("@")
                    if username:
                        url = f"https://x.com/{username}/status/{external_id}"
                author = str(
                    result.get("username")
                    or result.get("screen_name")
                    or result.get("author", {}).get("screen_name", "")
                    or "x"
                )
                items.append(
                    SourceItem(
                        research_profile_id=profile.id,
                        source=self.source_name,
                        external_id=external_id,
                        canonical_url=url,
                        author_name=author,
                        published_at=_utc_now(),
                        title=(text[:140] or external_id),
                        body_text=text[:4000],
                        engagement={
                            "likes": result.get("favorite_count", result.get("likes", 0)),
                            "replies": result.get("reply_count", 0),
                            "reposts": result.get("retweet_count", result.get("retweets", 0)),
                        },
                        raw_blob_url=_artifact_path(
                            settings=settings,
                            profile=profile,
                            source=self.source_name,
                            query=query,
                            external_id=external_id,
                            raw_payload={"query": query, "result": result},
                        ),
                        source_query=query,
                    )
                )
        return items
