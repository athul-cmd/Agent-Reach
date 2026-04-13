# -*- coding: utf-8 -*-
"""HTTP API for the research subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from agent_reach.research.health import build_health_report
from agent_reach.research.models import (
    CreatorWatch,
    IdeaCard,
    JobType,
    ResearchProfile,
    SourceItem,
    StyleProfile,
    TopicCluster,
    UserFeedbackEvent,
    WeeklyReport,
    WritingSample,
)
from agent_reach.research.store_protocol import ResearchStore
from agent_reach.research.verification import verify_all, verify_sources, verify_storage
from agent_reach.research.worker import ResearchScheduler, ResearchWorker


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _first_present(payload: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _profile_payload(profile: ResearchProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "name": profile.name,
        "persona_brief": profile.persona_brief,
        "niche_definition": profile.niche_definition,
        "must_track_topics": list(profile.must_track_topics),
        "excluded_topics": list(profile.excluded_topics),
        "target_audience": profile.target_audience,
        "desired_formats": list(profile.desired_formats),
        "status": profile.status,
        "created_at": _iso(profile.created_at),
        "updated_at": _iso(profile.updated_at),
    }


def _writing_sample_payload(sample: WritingSample) -> dict[str, Any]:
    return {
        "id": sample.id,
        "research_profile_id": sample.research_profile_id,
        "source_type": sample.source_type,
        "title": sample.title,
        "raw_text": sample.raw_text,
        "raw_blob_url": sample.raw_blob_url,
        "language": sample.language,
        "created_at": _iso(sample.created_at),
    }


def _style_profile_payload(style_profile: StyleProfile | None) -> dict[str, Any] | None:
    if style_profile is None:
        return None
    return {
        "id": style_profile.id,
        "research_profile_id": style_profile.research_profile_id,
        "tone_markers": list(style_profile.tone_markers),
        "hook_patterns": list(style_profile.hook_patterns),
        "structure_patterns": list(style_profile.structure_patterns),
        "preferred_topics": list(style_profile.preferred_topics),
        "avoided_topics": list(style_profile.avoided_topics),
        "evidence_preferences": list(style_profile.evidence_preferences),
        "embedding_version": style_profile.embedding_version,
        "raw_summary": style_profile.raw_summary,
        "generated_at": _iso(style_profile.generated_at),
    }


def _source_item_payload(item: SourceItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "research_profile_id": item.research_profile_id,
        "source": item.source,
        "external_id": item.external_id,
        "canonical_url": item.canonical_url,
        "author_name": item.author_name,
        "published_at": _iso(item.published_at),
        "title": item.title,
        "body_text": item.body_text,
        "engagement": dict(item.engagement),
        "raw_blob_url": item.raw_blob_url,
        "health_status": item.health_status,
        "source_query": item.source_query,
        "created_at": _iso(item.created_at),
    }


def _cluster_payload(cluster: TopicCluster) -> dict[str, Any]:
    return {
        "id": cluster.id,
        "research_profile_id": cluster.research_profile_id,
        "cluster_label": cluster.cluster_label,
        "cluster_summary": cluster.cluster_summary,
        "representative_terms": list(cluster.representative_terms),
        "supporting_item_ids": list(cluster.supporting_item_ids),
        "source_family_count": cluster.source_family_count,
        "freshness_score": cluster.freshness_score,
        "cluster_key": cluster.cluster_key,
        "final_score": cluster.final_score,
        "score_components": dict(cluster.score_components),
        "rank_snapshot_at": _iso(cluster.rank_snapshot_at),
    }


def _idea_payload(idea: IdeaCard) -> dict[str, Any]:
    return {
        "id": idea.id,
        "research_profile_id": idea.research_profile_id,
        "topic_cluster_id": idea.topic_cluster_id,
        "headline": idea.headline,
        "hook": idea.hook,
        "why_now": idea.why_now,
        "outline_md": idea.outline_md,
        "evidence_item_ids": list(idea.evidence_item_ids),
        "final_score": idea.final_score,
        "status": idea.status,
        "generated_at": _iso(idea.generated_at),
    }


def _creator_payload(creator: CreatorWatch) -> dict[str, Any]:
    return {
        "id": creator.id,
        "research_profile_id": creator.research_profile_id,
        "source": creator.source,
        "creator_external_id": creator.creator_external_id,
        "creator_name": creator.creator_name,
        "creator_url": creator.creator_url,
        "watch_reason": creator.watch_reason,
        "watch_score": creator.watch_score,
        "status": creator.status,
        "updated_at": _iso(creator.updated_at),
    }


def _report_payload(report: WeeklyReport | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "id": report.id,
        "research_profile_id": report.research_profile_id,
        "report_period_start": _iso(report.report_period_start),
        "report_period_end": _iso(report.report_period_end),
        "top_idea_ids": list(report.top_idea_ids),
        "top_creator_ids": list(report.top_creator_ids),
        "summary_md": report.summary_md,
        "published_at": _iso(report.published_at),
    }


def _job_payload(job: Any) -> dict[str, Any]:
    return {
        "id": job.id,
        "research_profile_id": job.research_profile_id,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "scheduled_for": _iso(job.scheduled_for),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
        "attempt_count": job.attempt_count,
        "input_snapshot": dict(job.input_snapshot),
        "error_summary": job.error_summary,
        "next_run_at": _iso(job.next_run_at),
        "heartbeat_at": _iso(job.heartbeat_at),
    }


class ResearchAPI:
    """Request dispatcher for the research system."""

    def __init__(
        self,
        store: ResearchStore,
        worker: ResearchWorker,
        scheduler: ResearchScheduler,
        api_access_token: str = "",
    ):
        self.store = store
        self.worker = worker
        self.scheduler = scheduler
        self.api_access_token = api_access_token.strip()

    def dispatch(
        self,
        method: str,
        raw_path: str,
        body: bytes,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        parsed = urlsplit(raw_path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        normalized_headers = {key.lower(): value for key, value in (headers or {}).items()}

        if path != "/health" and not self._authorized(normalized_headers):
            return HTTPStatus.UNAUTHORIZED, {"error": "Unauthorized."}

        payload = self._parse_json(body)

        if method == "GET" and path == "/health":
            return HTTPStatus.OK, {"ok": True}

        if method == "GET" and path == "/api/profile":
            profile = self._resolve_profile(query.get("profile_id", [None])[0])
            if profile is None:
                return HTTPStatus.NOT_FOUND, {"error": "No active research profile."}
            return HTTPStatus.OK, {"profile": _profile_payload(profile)}

        if method == "POST" and path == "/api/profile":
            profile = self._upsert_profile(payload)
            return HTTPStatus.OK, {"profile": _profile_payload(profile)}

        if method == "POST" and path == "/api/profile/writing-samples":
            profile = self._require_profile(payload.get("profile_id"))
            samples = self._create_writing_samples(profile.id, payload)
            return HTTPStatus.OK, {
                "added": len(samples),
                "samples": [_writing_sample_payload(sample) for sample in samples],
            }

        if method == "POST" and path == "/api/profile/linkedin-import":
            profile = self._require_profile(payload.get("profile_id"))
            samples = self._import_linkedin_posts(profile.id, payload)
            return HTTPStatus.OK, {
                "imported": len(samples),
                "samples": [_writing_sample_payload(sample) for sample in samples],
            }

        if method == "GET" and path == "/api/library/source-items":
            profile = self._require_profile(query.get("profile_id", [None])[0])
            limit = self._parse_limit(query.get("limit", ["50"])[0], 50)
            items = self.store.list_source_items(profile.id, limit=limit)
            return HTTPStatus.OK, {"items": [_source_item_payload(item) for item in items]}

        if method == "GET" and path == "/api/library/clusters":
            profile = self._require_profile(query.get("profile_id", [None])[0])
            limit = self._parse_limit(query.get("limit", ["50"])[0], 50)
            clusters = self.store.list_clusters(profile.id)[:limit]
            return HTTPStatus.OK, {"clusters": [_cluster_payload(cluster) for cluster in clusters]}

        if method == "GET" and path == "/api/library/ideas":
            profile = self._require_profile(query.get("profile_id", [None])[0])
            status = query.get("status", [None])[0]
            limit = self._parse_limit(query.get("limit", ["50"])[0], 50)
            ideas = self.store.list_idea_cards(profile.id, status=status, limit=limit)
            return HTTPStatus.OK, {"ideas": [_idea_payload(idea) for idea in ideas]}

        if method == "GET" and path == "/api/library/creators":
            profile = self._require_profile(query.get("profile_id", [None])[0])
            limit = self._parse_limit(query.get("limit", ["20"])[0], 20)
            creators = self.store.list_creator_watchlist(profile.id, limit=limit)
            return HTTPStatus.OK, {"creators": [_creator_payload(creator) for creator in creators]}

        if method == "GET" and path == "/api/reports/latest":
            profile = self._require_profile(query.get("profile_id", [None])[0])
            report = self.store.get_latest_report(profile.id)
            return HTTPStatus.OK, {"report": _report_payload(report)}

        if method == "GET" and path == "/api/jobs":
            profile = self._require_profile(query.get("profile_id", [None])[0])
            limit = self._parse_limit(query.get("limit", ["25"])[0], 25)
            jobs = self.store.list_jobs(profile.id, limit=limit)
            return HTTPStatus.OK, {"jobs": [_job_payload(job) for job in jobs]}

        if method == "GET" and path == "/api/system/health":
            profile = self._resolve_profile(query.get("profile_id", [None])[0])
            return HTTPStatus.OK, {
                "health": build_health_report(
                    settings=self.worker.settings,
                    store=self.store,
                    adapters=self.worker.adapters,
                    profile_id=profile.id if profile is not None else None,
                )
            }

        if method == "POST" and path == "/api/system/verify":
            profile = self._resolve_profile(payload.get("profile_id"))
            mode = str(payload.get("mode") or "all").strip().lower()
            run_collect = bool(payload.get("run_collect"))
            limit = self._parse_limit(str(payload.get("limit") or "1"), 1)
            if mode == "storage":
                return HTTPStatus.OK, {"verification": verify_storage(self.worker.settings)}
            if mode == "sources":
                return HTTPStatus.OK, {
                    "verification": verify_sources(
                        settings=self.worker.settings,
                        profile=profile,
                        adapters=self.worker.adapters,
                        run_collect=run_collect,
                        limit=limit,
                    )
                }
            if mode == "all":
                return HTTPStatus.OK, {
                    "verification": verify_all(
                        settings=self.worker.settings,
                        profile=profile,
                        adapters=self.worker.adapters,
                        run_source_collect=run_collect,
                        source_limit=limit,
                    )
                }
            raise ValueError("Verification mode must be one of: storage, sources, all.")

        if method == "GET" and path == "/api/dashboard":
            profile = self._resolve_profile(query.get("profile_id", [None])[0])
            dashboard = self._build_dashboard(profile.id if profile is not None else None)
            return HTTPStatus.OK, dashboard

        if method == "POST" and path.startswith("/api/ideas/"):
            return self._handle_idea_action(path, payload)

        if method == "POST" and path == "/api/runs/manual":
            profile = self._require_profile(payload.get("profile_id"))
            result = self._run_manual_job(profile.id, payload)
            return HTTPStatus.OK, result

        return HTTPStatus.NOT_FOUND, {"error": f"Unknown route: {method} {path}"}

    def _authorized(self, headers: dict[str, str]) -> bool:
        if not self.api_access_token:
            return True
        provided = headers.get("x-research-api-token", "").strip()
        if provided and provided == self.api_access_token:
            return True
        authorization = headers.get("authorization", "").strip()
        if authorization.startswith("Bearer "):
            return authorization[7:].strip() == self.api_access_token
        return False

    def _parse_json(self, body: bytes) -> dict[str, Any]:
        if not body:
            return {}
        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON body: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object.")
        return parsed

    def _resolve_profile(self, profile_id: str | None) -> ResearchProfile | None:
        if profile_id:
            return self.store.get_profile(profile_id)
        return self.store.get_latest_profile()

    def _require_profile(self, profile_id: str | None) -> ResearchProfile:
        profile = self._resolve_profile(profile_id)
        if profile is None:
            raise ValueError("No active research profile.")
        return profile

    def _parse_limit(self, raw_value: str | None, default: int) -> int:
        try:
            if raw_value is None:
                return default
            parsed = int(raw_value)
        except (TypeError, ValueError):
            return default
        return max(1, min(parsed, 250))

    def _upsert_profile(self, payload: dict[str, Any]) -> ResearchProfile:
        current = self.store.get_latest_profile()
        profile = current or ResearchProfile(
            name="",
            persona_brief="",
            niche_definition="",
        )
        profile.name = str(payload.get("name") or profile.name).strip()
        profile.persona_brief = str(
            payload.get("persona_brief") or payload.get("persona") or profile.persona_brief
        ).strip()
        profile.niche_definition = str(
            payload.get("niche_definition") or payload.get("niche") or profile.niche_definition
        ).strip()
        profile.target_audience = str(
            payload.get("target_audience") or payload.get("audience") or profile.target_audience
        ).strip()
        must_track_value = _first_present(payload, ["must_track_topics", "topics", "topic"])
        excluded_value = _first_present(payload, ["excluded_topics", "exclude"])
        formats_value = _first_present(payload, ["desired_formats", "formats", "format"])
        if must_track_value is not None:
            profile.must_track_topics = _coerce_list(must_track_value)
        if excluded_value is not None:
            profile.excluded_topics = _coerce_list(excluded_value)
        if formats_value is not None:
            profile.desired_formats = _coerce_list(formats_value)
        if not profile.name or not profile.persona_brief or not profile.niche_definition:
            raise ValueError("Profile requires name, persona_brief, and niche_definition.")
        profile.updated_at = datetime.now(profile.updated_at.tzinfo)
        self.store.upsert_profile(profile)
        return profile

    def _create_writing_samples(
        self,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[WritingSample]:
        raw_samples = payload.get("samples")
        if isinstance(raw_samples, list):
            sample_inputs = [item for item in raw_samples if isinstance(item, dict)]
        else:
            sample_inputs = [payload]
        created: list[WritingSample] = []
        for item in sample_inputs:
            raw_text = str(item.get("raw_text") or item.get("text") or "").strip()
            title = str(item.get("title") or "").strip()
            if not raw_text or not title:
                continue
            sample = WritingSample(
                research_profile_id=profile_id,
                source_type=str(item.get("source_type") or "uploaded"),
                title=title,
                raw_text=raw_text,
                raw_blob_url=str(item.get("raw_blob_url") or item.get("url") or ""),
                language=str(item.get("language") or "en"),
            )
            self.store.add_writing_sample(sample)
            created.append(sample)
        if not created:
            raise ValueError("No valid writing samples found in request.")
        return created

    def _import_linkedin_posts(
        self,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[WritingSample]:
        posts = payload.get("posts")
        if not isinstance(posts, list):
            raise ValueError("LinkedIn import requires a `posts` array.")
        created: list[WritingSample] = []
        for index, post in enumerate(posts, start=1):
            if not isinstance(post, dict):
                continue
            text = str(post.get("text") or post.get("raw_text") or "").strip()
            if not text:
                continue
            title = str(post.get("title") or f"LinkedIn Post {index}").strip()
            sample = WritingSample(
                research_profile_id=profile_id,
                source_type="linkedin",
                title=title,
                raw_text=text,
                raw_blob_url=str(post.get("url") or ""),
                language=str(post.get("language") or "en"),
            )
            self.store.add_writing_sample(sample)
            created.append(sample)
        if not created:
            raise ValueError("No valid LinkedIn posts found in request.")
        return created

    def _handle_idea_action(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        parts = path.split("/")
        if len(parts) != 5:
            return HTTPStatus.NOT_FOUND, {"error": f"Unknown route: POST {path}"}
        _, api_segment, ideas_segment, idea_id, action = parts
        if api_segment != "api" or ideas_segment != "ideas" or not idea_id:
            return HTTPStatus.NOT_FOUND, {"error": f"Unknown route: POST {path}"}
        profile = self._require_profile(payload.get("profile_id"))
        if action == "save":
            event_type = "save"
            status = "saved"
        elif action == "discard":
            event_type = "discard"
            status = "discarded"
        elif action == "feedback":
            event_type = "feedback"
            status = None
        else:
            return HTTPStatus.NOT_FOUND, {"error": f"Unknown route: POST {path}"}
        feedback = UserFeedbackEvent(
            research_profile_id=profile.id,
            idea_card_id=idea_id,
            event_type=event_type,
            event_payload={"note": str(payload.get("note") or "").strip()} if payload.get("note") else {},
        )
        self.store.add_feedback(feedback)
        if status is not None:
            self.store.set_idea_status(idea_id, status)
        return HTTPStatus.OK, {
            "ok": True,
            "idea_id": idea_id,
            "event": event_type,
            "status": status,
        }

    def _run_manual_job(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        job_name = str(payload.get("job") or "all")
        if job_name == "all":
            results = self.worker.run_full_cycle(profile_id)
            return {"job": "all", "result": results}
        job_type = JobType(job_name)
        return {"job": job_type.value, "result": self.worker.run_job(job_type, profile_id)}

    def _build_dashboard(self, profile_id: str | None) -> dict[str, Any]:
        if not profile_id:
            return {
                "generated_at": _iso(datetime.now(timezone.utc)),
                "system_health": build_health_report(
                    settings=self.worker.settings,
                    store=self.store,
                    adapters=self.worker.adapters,
                    profile_id=None,
                ),
                "profile": None,
                "style_profile": None,
                "report": None,
                "source_items": [],
                "clusters": [],
                "ideas": [],
                "creators": [],
                "jobs": [],
                "metrics": {
                    "source_item_count": 0,
                    "cluster_count": 0,
                    "idea_count": 0,
                    "creator_count": 0,
                },
            }
        profile = self.store.get_profile(profile_id)
        style_profile = self.store.get_latest_style_profile(profile_id)
        report = self.store.get_latest_report(profile_id)
        items = self.store.list_source_items(profile_id, limit=50)
        clusters = self.store.list_clusters(profile_id)[:25]
        ideas = self.store.list_idea_cards(profile_id, limit=25)
        creators = self.store.list_creator_watchlist(profile_id, limit=12)
        jobs = self.store.list_jobs(profile_id, limit=12)
        return {
            "generated_at": _iso(datetime.now(timezone.utc)),
            "system_health": build_health_report(
                settings=self.worker.settings,
                store=self.store,
                adapters=self.worker.adapters,
                profile_id=profile_id,
            ),
            "profile": _profile_payload(profile),
            "style_profile": _style_profile_payload(style_profile),
            "report": _report_payload(report),
            "source_items": [_source_item_payload(item) for item in items],
            "clusters": [_cluster_payload(cluster) for cluster in clusters],
            "ideas": [_idea_payload(idea) for idea in ideas],
            "creators": [_creator_payload(creator) for creator in creators],
            "jobs": [_job_payload(job) for job in jobs],
            "metrics": {
                "source_item_count": len(items),
                "cluster_count": len(clusters),
                "idea_count": len(ideas),
                "creator_count": len(creators),
            },
        }


class _ResearchHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], app: ResearchAPI):
        super().__init__(server_address, _ResearchAPIHandler)
        self.app = app


class _ResearchAPIHandler(BaseHTTPRequestHandler):
    server_version = "AgentReachResearchAPI/0.1"

    def do_OPTIONS(self) -> None:
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_HEAD(self) -> None:
        self._dispatch()

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        body = self._read_body()
        try:
            status, payload = self.server.app.dispatch(  # type: ignore[attr-defined]
                self.command,
                self.path,
                body,
                headers={key: value for key, value in self.headers.items()},
            )
        except ValueError as exc:
            status, payload = HTTPStatus.BAD_REQUEST, {"error": str(exc)}
        except Exception as exc:
            status, payload = HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)}
        self._send_json(status, payload)

    def _read_body(self) -> bytes:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return b""
        return self.rfile.read(int(content_length))

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Research-Api-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)


def run_api_server(
    host: str,
    port: int,
    store: ResearchStore,
    worker: ResearchWorker,
    scheduler: ResearchScheduler,
    api_access_token: str = "",
) -> None:
    """Start the research HTTP API."""
    server = _ResearchHTTPServer(
        (host, port),
        ResearchAPI(
            store=store,
            worker=worker,
            scheduler=scheduler,
            api_access_token=api_access_token,
        ),
    )
    print(f"Research API listening on http://{host}:{port}")
    server.serve_forever()
