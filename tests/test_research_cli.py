# -*- coding: utf-8 -*-
"""Tests for the research CLI run modes."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta

from agent_reach.research.cli import _handle_run
from agent_reach.research.models import JobRun, JobStatus, JobType, utc_now


class _FakeStore:
    def __init__(self, jobs: list[JobRun]):
        self.jobs = {job.id: job for job in jobs}
        self.completed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.claim_calls: list[dict[str, object]] = []

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def claim_due_jobs(self, now, *, limit: int, lease_for: timedelta, lease_owner: str):
        self.claim_calls.append(
            {
                "now": now,
                "limit": limit,
                "lease_for": lease_for,
                "lease_owner": lease_owner,
            }
        )
        return list(self.jobs.values())[:limit]

    def complete_job(self, job_id: str, finished_at):
        self.completed.append(job_id)
        self.jobs[job_id].status = JobStatus.SUCCEEDED
        self.jobs[job_id].finished_at = finished_at

    def fail_job(self, job_id: str, finished_at, error_summary: str):
        self.failed.append((job_id, error_summary))
        self.jobs[job_id].status = JobStatus.FAILED
        self.jobs[job_id].finished_at = finished_at
        self.jobs[job_id].error_summary = error_summary


class _FakeWorker:
    def __init__(self, *, fail_types: set[JobType] | None = None):
        self.fail_types = fail_types or set()
        self.calls: list[tuple[JobType, str]] = []

    def run_job(self, job_type: JobType, profile_id: str):
        self.calls.append((job_type, profile_id))
        if job_type in self.fail_types:
            raise RuntimeError(f"boom:{job_type.value}")
        return {"job_type": job_type.value, "profile_id": profile_id}


def _job(job_type: JobType, profile_id: str = "profile_123") -> JobRun:
    return JobRun(
        research_profile_id=profile_id,
        job_type=job_type,
        status=JobStatus.PENDING,
        scheduled_for=utc_now(),
    )


def test_handle_run_dispatch_claims_jobs_without_execution(capsys):
    job = _job(JobType.COLLECT_SOURCES)
    store = _FakeStore([job])
    worker = _FakeWorker()
    args = argparse.Namespace(
        research_run_command="dispatch",
        limit=1,
        lease_seconds=600,
        lease_owner="cli-test",
        execute=False,
    )

    _handle_run(args, store, worker, scheduler=None, profile_id="")

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"claimed": 1, "jobs": [job.id]}
    assert store.claim_calls[0]["limit"] == 1
    assert store.claim_calls[0]["lease_for"] == timedelta(seconds=600)
    assert store.claim_calls[0]["lease_owner"] == "cli-test"
    assert worker.calls == []


def test_handle_run_dispatch_executes_successes_and_failures(capsys):
    success = _job(JobType.COLLECT_SOURCES)
    failure = _job(JobType.DISCOVER_CREATORS)
    store = _FakeStore([success, failure])
    worker = _FakeWorker(fail_types={JobType.DISCOVER_CREATORS})
    args = argparse.Namespace(
        research_run_command="dispatch",
        limit=2,
        lease_seconds=1200,
        lease_owner="cli-test",
        execute=True,
    )

    _handle_run(args, store, worker, scheduler=None, profile_id="")

    payload = json.loads(capsys.readouterr().out)
    assert payload["claimed"] == 2
    assert payload["executed"][0]["status"] == "succeeded"
    assert payload["executed"][1]["status"] == "failed"
    assert payload["executed"][1]["error"] == "boom:discover_creators"
    assert store.completed == [success.id]
    assert store.failed == [(failure.id, "boom:discover_creators")]


def test_handle_run_job_executes_one_claimed_job(capsys):
    job = _job(JobType.GENERATE_IDEAS)
    store = _FakeStore([job])
    worker = _FakeWorker()
    args = argparse.Namespace(
        research_run_command="job",
        job_run_id=job.id,
    )

    _handle_run(args, store, worker, scheduler=None, profile_id="")

    payload = json.loads(capsys.readouterr().out)
    assert payload["job"] == "generate_ideas"
    assert payload["job_run_id"] == job.id
    assert payload["result"]["profile_id"] == job.research_profile_id
    assert store.completed == [job.id]
