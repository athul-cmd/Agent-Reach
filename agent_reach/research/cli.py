# -*- coding: utf-8 -*-
"""CLI integration for the research subsystem."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import time
from pathlib import Path
import textwrap

from agent_reach.research.api import run_api_server
from agent_reach.research.health import build_health_report
from agent_reach.research.maintenance import cleanup_artifacts, prepare_storage, storage_status
from agent_reach.research.models import JobType, ResearchProfile, UserFeedbackEvent, WritingSample
from agent_reach.research.runtime import ResearchWorkerService, load_worker_status
from agent_reach.research.settings import ResearchSettings
from agent_reach.research.snapshot import write_nodepad_snapshot
from agent_reach.research.store_factory import create_research_store
from agent_reach.research.store_protocol import ResearchStore
from agent_reach.research.verification import verify_all, verify_sources, verify_storage
from agent_reach.research.worker import ResearchScheduler, ResearchWorker


def register_research_parser(subparsers: argparse._SubParsersAction) -> None:
    """Attach the research command tree to the main CLI."""
    research = subparsers.add_parser("research", help="Run the content research studio backend")
    research.add_argument("--db", default="", help="Override research database path")
    research.add_argument(
        "--db-backend",
        default="",
        choices=["", "sqlite", "postgres", "supabase"],
        help="Override the research database backend",
    )
    research.add_argument("--db-dsn", default="", help="Override the Postgres DSN")

    research_sub = research.add_subparsers(dest="research_command", required=True)

    research_sub.add_parser("init", help="Initialize local research settings and store")

    storage = research_sub.add_parser("storage", help="Inspect and maintain configured storage backends")
    storage_sub = storage.add_subparsers(dest="research_storage_command", required=True)
    storage_sub.add_parser("status", help="Show effective database and blob storage settings")
    storage_sub.add_parser("prepare", help="Initialize the configured database schema and storage roots")
    storage_cleanup = storage_sub.add_parser("cleanup", help="Delete stale raw artifacts or snapshots")
    storage_cleanup.add_argument(
        "--kind",
        default="raw",
        choices=["raw", "snapshots", "all"],
        help="Select which artifact family to clean",
    )
    storage_cleanup.add_argument(
        "--older-than-days",
        type=int,
        required=True,
        help="Delete artifacts older than this many days",
    )
    storage_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matching artifacts without deleting them",
    )

    research_sub.add_parser("health", help="Show combined worker, job, source, and storage health")

    verify = research_sub.add_parser("verify", help="Run deployment verification and smoke checks")
    verify_sub = verify.add_subparsers(dest="research_verify_command", required=True)
    verify_sub.add_parser("storage", help="Run live DB/blob connectivity checks")
    verify_sources_cmd = verify_sub.add_parser("sources", help="Check source adapter readiness")
    verify_sources_cmd.add_argument(
        "--run-collect",
        action="store_true",
        help="Perform one live collect attempt per available source",
    )
    verify_sources_cmd.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Item limit for live source smoke collection",
    )
    verify_all_cmd = verify_sub.add_parser("all", help="Run storage checks and source verification")
    verify_all_cmd.add_argument(
        "--run-collect",
        action="store_true",
        help="Perform one live collect attempt per available source",
    )
    verify_all_cmd.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Item limit for live source smoke collection",
    )

    profile = research_sub.add_parser("profile", help="Manage the research profile")
    profile_sub = profile.add_subparsers(dest="research_profile_command", required=True)
    profile_set = profile_sub.add_parser("set", help="Create or update the active profile")
    profile_set.add_argument("--name", required=True)
    profile_set.add_argument("--persona", required=True)
    profile_set.add_argument("--niche", required=True)
    profile_set.add_argument("--audience", default="")
    profile_set.add_argument("--topic", action="append", default=[])
    profile_set.add_argument("--exclude", action="append", default=[])
    profile_set.add_argument("--format", action="append", default=[])
    profile_sub.add_parser("show", help="Show the active profile")

    sample = research_sub.add_parser("sample", help="Manage writing samples")
    sample_sub = sample.add_subparsers(dest="research_sample_command", required=True)
    sample_add = sample_sub.add_parser("add", help="Add a writing sample from a file")
    sample_add.add_argument("path")
    sample_add.add_argument("--title", default="")
    sample_add.add_argument("--source-type", default="uploaded")
    sample_sub.add_parser("list", help="List stored writing samples")

    run = research_sub.add_parser("run", help="Run research jobs")
    run_sub = run.add_subparsers(dest="research_run_command", required=True)
    run_once = run_sub.add_parser("once", help="Run one job or the full pipeline immediately")
    run_once.add_argument(
        "--job",
        default="all",
        choices=["all"] + [job.value for job in JobType],
    )
    run_schedule = run_sub.add_parser("schedule", help="Run the scheduler loop")
    run_schedule.add_argument("--iterations", type=int, default=0, help="0 means run forever")
    run_schedule.add_argument(
        "--sleep-seconds",
        type=int,
        default=5,
        help="Delay between scheduler ticks for local execution",
    )
    run_dispatch = run_sub.add_parser("dispatch", help="Claim due jobs for external runners or execute them locally")
    run_dispatch.add_argument("--limit", type=int, default=4, help="Maximum number of due jobs to claim")
    run_dispatch.add_argument(
        "--lease-owner",
        default="cli-dispatch",
        help="Lease owner marker written to claimed jobs",
    )
    run_dispatch.add_argument(
        "--lease-seconds",
        type=int,
        default=20 * 60,
        help="How long claimed jobs remain leased before becoming claimable again",
    )
    run_dispatch.add_argument(
        "--execute",
        action="store_true",
        help="Execute claimed jobs immediately in this process instead of only printing IDs",
    )
    run_job = run_sub.add_parser("job", help="Execute one claimed job by ID")
    run_job.add_argument("--job-run-id", required=True, help="Job run ID to execute")

    serve = research_sub.add_parser("serve", help="Run the research HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8877)

    worker_cmd = research_sub.add_parser("worker", help="Run or inspect the persistent research worker")
    worker_sub = worker_cmd.add_subparsers(dest="research_worker_command", required=True)
    worker_run = worker_sub.add_parser("run", help="Run the persistent scheduler worker")
    worker_run.add_argument("--profile-id", default="", help="Pin the worker to one profile ID")
    worker_run.add_argument(
        "--sleep-seconds",
        type=int,
        default=0,
        help="Override worker heartbeat sleep. Defaults to scheduler_heartbeat_seconds.",
    )
    worker_run.add_argument(
        "--max-ticks",
        type=int,
        default=0,
        help="Stop after this many ticks. Use 0 to run until interrupted.",
    )
    worker_sub.add_parser("status", help="Show the last persisted worker runtime status")

    report = research_sub.add_parser("report", help="Read or export reports")
    report_sub = report.add_subparsers(dest="research_report_command", required=True)
    report_latest = report_sub.add_parser("latest", help="Show the latest weekly report")
    report_latest.add_argument("--export-nodepad", default="", help="Write a .nodepad snapshot")

    feedback = research_sub.add_parser("feedback", help="Record idea feedback")
    feedback.add_argument("idea_id")
    feedback.add_argument("event_type", choices=["save", "discard", "feedback"])
    feedback.add_argument("--note", default="")


def handle_research_command(args: argparse.Namespace) -> None:
    """Execute the research command tree."""
    settings = ResearchSettings.load()
    if args.db:
        settings.db_path = args.db
    if args.db_backend:
        settings.db_backend = args.db_backend
    if args.db_dsn:
        settings.db_dsn = args.db_dsn

    if args.research_command == "init":
        store = create_research_store(settings)
        summary = prepare_storage(settings, store)
        config_path = settings.save()
        print(f"Research settings initialized: {config_path}")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    if args.research_command == "storage":
        _handle_storage(args, settings)
        return

    store = create_research_store(settings)
    worker = ResearchWorker(store=store, settings=settings)

    if args.research_command == "health":
        profile = store.get_latest_profile()
        print(
            json.dumps(
                build_health_report(
                    settings=settings,
                    store=store,
                    adapters=worker.adapters,
                    profile_id=profile.id if profile is not None else None,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.research_command == "verify":
        profile = store.get_latest_profile()
        _handle_verify(args, settings, store, worker, profile)
        return

    prepare_storage(settings, store)
    scheduler = ResearchScheduler(store=store, settings=settings, worker=worker)

    profile = store.get_latest_profile()
    if args.research_command == "profile":
        _handle_profile(args, store, profile)
        return

    if args.research_command == "serve":
        if profile is not None:
            scheduler.bootstrap_profile(profile.id)
        run_api_server(
            args.host,
            args.port,
            store=store,
            worker=worker,
            scheduler=scheduler,
            api_access_token=settings.api_access_token,
        )
        return

    if args.research_command == "worker":
        _handle_worker(args, settings, store, worker, scheduler)
        return

    if args.research_command == "run" and args.research_run_command in {"job", "dispatch"}:
        _handle_run(args, store, worker, scheduler, "")
        return

    if profile is None:
        raise SystemExit("No active research profile. Run `agent-reach research profile set ...` first.")

    if args.research_command == "sample":
        _handle_sample(args, store, profile.id)
        return

    if args.research_command == "run":
        _handle_run(args, store, worker, scheduler, profile.id)
        return

    if args.research_command == "report":
        _handle_report(args, store, profile.id)
        return

    if args.research_command == "feedback":
        feedback = UserFeedbackEvent(
            research_profile_id=profile.id,
            idea_card_id=args.idea_id,
            event_type=args.event_type,
            event_payload={"note": args.note} if args.note else {},
        )
        store.add_feedback(feedback)
        if args.event_type in {"save", "discard"}:
            store.set_idea_status(args.idea_id, "saved" if args.event_type == "save" else "discarded")
        print(f"Recorded feedback event: {feedback.event_type} for {feedback.idea_card_id}")
        return


def _handle_storage(
    args: argparse.Namespace,
    settings: ResearchSettings,
) -> None:
    if args.research_storage_command == "status":
        print(json.dumps(storage_status(settings), indent=2, ensure_ascii=False))
        return

    if args.research_storage_command == "prepare":
        store = create_research_store(settings)
        print(json.dumps(prepare_storage(settings, store), indent=2, ensure_ascii=False))
        return

    if args.research_storage_command == "cleanup":
        result = cleanup_artifacts(
            settings,
            kind=args.kind,
            older_than_days=args.older_than_days,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return


def _handle_worker(
    args: argparse.Namespace,
    settings: ResearchSettings,
    store: ResearchStore,
    worker: ResearchWorker,
    scheduler: ResearchScheduler,
) -> None:
    if args.research_worker_command == "status":
        payload = load_worker_status(settings) or {"state": "unknown", "note": "No worker status file found."}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    service = ResearchWorkerService(
        store=store,
        settings=settings,
        worker=worker,
        scheduler=scheduler,
        sleep_seconds=args.sleep_seconds or settings.scheduler_heartbeat_seconds,
    )
    service.initialize()
    profile_id = args.profile_id or ""
    if not profile_id and store.get_latest_profile() is None:
        print("No active profile yet. Worker will stay idle until a profile is created.")
    print("Starting persistent research worker. Press Ctrl+C to stop.")
    service.run_forever(profile_id=profile_id or None, max_ticks=args.max_ticks)


def _handle_verify(
    args: argparse.Namespace,
    settings: ResearchSettings,
    store: ResearchStore,
    worker: ResearchWorker,
    profile: ResearchProfile | None,
) -> None:
    if args.research_verify_command == "storage":
        print(json.dumps(verify_storage(settings), indent=2, ensure_ascii=False))
        return

    if args.research_verify_command == "sources":
        print(
            json.dumps(
                verify_sources(
                    settings=settings,
                    profile=profile,
                    adapters=worker.adapters,
                    run_collect=args.run_collect,
                    limit=args.limit,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.research_verify_command == "all":
        print(
            json.dumps(
                verify_all(
                    settings=settings,
                    profile=profile,
                    adapters=worker.adapters,
                    run_source_collect=args.run_collect,
                    source_limit=args.limit,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return


def _handle_profile(
    args: argparse.Namespace,
    store: ResearchStore,
    profile: ResearchProfile | None,
) -> None:
    if args.research_profile_command == "show":
        if profile is None:
            raise SystemExit("No active research profile.")
        print(_profile_summary(profile))
        return

    if profile is None:
        profile = ResearchProfile(
            name=args.name,
            persona_brief=args.persona,
            niche_definition=args.niche,
            must_track_topics=args.topic,
            excluded_topics=args.exclude,
            target_audience=args.audience,
            desired_formats=args.format,
        )
    else:
        profile.name = args.name
        profile.persona_brief = args.persona
        profile.niche_definition = args.niche
        profile.must_track_topics = list(args.topic)
        profile.excluded_topics = list(args.exclude)
        profile.target_audience = args.audience
        profile.desired_formats = list(args.format)
        profile.updated_at = datetime.now(profile.updated_at.tzinfo)
    store.upsert_profile(profile)
    print("Active research profile saved.")
    print(_profile_summary(profile))


def _handle_sample(args: argparse.Namespace, store: ResearchStore, profile_id: str) -> None:
    if args.research_sample_command == "list":
        samples = store.list_writing_samples(profile_id)
        if not samples:
            print("No writing samples stored.")
            return
        for sample in samples:
            print(f"- {sample.id}: {sample.title} ({sample.source_type})")
        return

    sample_path = Path(args.path)
    if not sample_path.exists():
        raise SystemExit(f"Sample file does not exist: {sample_path}")
    raw_text = sample_path.read_text(encoding="utf-8")
    title = args.title or sample_path.stem
    sample = WritingSample(
        research_profile_id=profile_id,
        source_type=args.source_type,
        title=title,
        raw_text=raw_text,
        raw_blob_url=str(sample_path.resolve()),
    )
    store.add_writing_sample(sample)
    print(f"Added writing sample: {sample.title}")


def _handle_run(
    args: argparse.Namespace,
    store: ResearchStore,
    worker: ResearchWorker,
    scheduler: ResearchScheduler,
    profile_id: str,
) -> None:
    if args.research_run_command == "once":
        if args.job == "all":
            results = worker.run_full_cycle(profile_id)
            print("Completed full research cycle.")
            for key, value in results.items():
                print(f"- {key}: {value}")
            return
        result = worker.run_job(JobType(args.job), profile_id)
        print(f"Completed job: {args.job}")
        print(result)
        return

    if args.research_run_command == "job":
        job = store.get_job(args.job_run_id)
        if job is None:
            raise SystemExit(f"Unknown job run: {args.job_run_id}")
        try:
            result = worker.run_job(job.job_type, job.research_profile_id)
        except Exception as exc:
            store.fail_job(job.id, datetime.now(timezone.utc), str(exc))
            raise
        store.complete_job(job.id, datetime.now(timezone.utc))
        print(json.dumps({"job": job.job_type.value, "job_run_id": job.id, "result": result}, ensure_ascii=False))
        return

    if args.research_run_command == "dispatch":
        claimed = store.claim_due_jobs(
            datetime.now(timezone.utc),
            limit=args.limit,
            lease_for=timedelta(seconds=max(60, args.lease_seconds)),
            lease_owner=args.lease_owner,
        )
        if not args.execute:
            print(
                json.dumps(
                    {
                        "claimed": len(claimed),
                        "jobs": [job.id for job in claimed],
                    },
                    ensure_ascii=False,
                )
            )
            return
        executed = []
        for job in claimed:
            try:
                result = worker.run_job(job.job_type, job.research_profile_id)
            except Exception as exc:
                store.fail_job(job.id, datetime.now(timezone.utc), str(exc))
                executed.append({"job_run_id": job.id, "status": "failed", "error": str(exc)})
                continue
            store.complete_job(job.id, datetime.now(timezone.utc))
            executed.append({"job_run_id": job.id, "status": "succeeded", "result": result})
        print(json.dumps({"claimed": len(claimed), "executed": executed}, ensure_ascii=False))
        return

    iterations = args.iterations
    tick_count = 0
    print("Starting research scheduler. Press Ctrl+C to stop.")
    while True:
        result = scheduler.tick(profile_id)
        tick_count += 1
        if result:
            print(f"[tick {tick_count}] {result}")
        else:
            print(f"[tick {tick_count}] no due jobs")
        if iterations and tick_count >= iterations:
            return
        time.sleep(args.sleep_seconds)


def _handle_report(args: argparse.Namespace, store: ResearchStore, profile_id: str) -> None:
    report = store.get_latest_report(profile_id)
    if report is None:
        raise SystemExit("No weekly report has been published yet.")
    print(report.summary_md)
    if args.export_nodepad:
        ideas = [idea for idea in store.list_idea_cards(profile_id) if idea.id in set(report.top_idea_ids)]
        cluster_ids = {idea.topic_cluster_id for idea in ideas}
        clusters = [cluster for cluster in store.list_clusters(profile_id) if cluster.id in cluster_ids]
        target = Path(args.export_nodepad)
        write_nodepad_snapshot(target, report, ideas, clusters)
        print(f"Nodepad snapshot exported: {target}")


def _profile_summary(profile: ResearchProfile) -> str:
    return textwrap.dedent(
        f"""
        Profile ID: {profile.id}
        Name: {profile.name}
        Persona: {profile.persona_brief}
        Niche: {profile.niche_definition}
        Audience: {profile.target_audience or 'n/a'}
        Must-track topics: {', '.join(profile.must_track_topics) or 'n/a'}
        Excluded topics: {', '.join(profile.excluded_topics) or 'n/a'}
        Formats: {', '.join(profile.desired_formats) or 'n/a'}
        """
    ).strip()
