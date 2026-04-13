# -*- coding: utf-8 -*-
"""Export research reports as Nodepad-compatible snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from agent_reach.research.models import IdeaCard, TopicCluster, WeeklyReport

SNAPSHOT_VERSION = 2


def report_to_nodepad_snapshot(
    report: WeeklyReport,
    ideas: Sequence[IdeaCard],
    clusters: Sequence[TopicCluster],
) -> dict:
    """Convert a weekly report into a portable Nodepad-style project payload."""
    cluster_by_id = {cluster.id: cluster for cluster in clusters}
    blocks = []
    root_id = f"report-{report.id}"
    blocks.append(
        {
            "id": root_id,
            "text": f"Weekly Research Digest ({report.report_period_start.date()} to "
            f"{report.report_period_end.date()})",
            "timestamp": int(report.published_at.timestamp() * 1000),
            "contentType": "thesis",
            "category": "weekly digest",
            "annotation": report.summary_md,
            "confidence": None,
            "sources": [],
            "influencedBy": [],
            "isUnrelated": False,
            "isPinned": True,
        }
    )

    added_clusters = set()
    for idea in ideas:
        cluster = cluster_by_id.get(idea.topic_cluster_id)
        block_id = f"idea-{idea.id}"
        blocks.append(
            {
                "id": block_id,
                "text": idea.headline,
                "timestamp": int(idea.generated_at.timestamp() * 1000),
                "contentType": "idea",
                "category": "ranked idea",
                "annotation": (
                    f"Hook: {idea.hook}\n\nWhy now: {idea.why_now}\n\n{idea.outline_md}".strip()
                ),
                "confidence": idea.final_score,
                "sources": [],
                "influencedBy": [root_id] + ([f"cluster-{cluster.id}"] if cluster else []),
                "isUnrelated": False,
                "isPinned": idea.status == "saved",
            }
        )
        if cluster and cluster.id not in added_clusters:
            added_clusters.add(cluster.id)
            blocks.append(
                {
                    "id": f"cluster-{cluster.id}",
                    "text": cluster.cluster_label,
                    "timestamp": int(cluster.rank_snapshot_at.timestamp() * 1000),
                    "contentType": "claim",
                    "category": "topic cluster",
                    "annotation": cluster.cluster_summary,
                    "confidence": cluster.final_score,
                    "sources": [],
                    "influencedBy": [root_id],
                    "isUnrelated": False,
                    "isPinned": False,
                }
            )

    return {
        "version": SNAPSHOT_VERSION,
        "exportedAt": int(report.published_at.timestamp() * 1000),
        "project": {
            "id": report.id,
            "name": "Content Research Studio Snapshot",
            "blocks": blocks,
            "collapsedIds": [],
            "ghostNotes": [],
            "lastGhostTexts": [],
            "lastGhostBlockCount": len(blocks),
            "lastGhostTimestamp": int(report.published_at.timestamp() * 1000),
        },
    }


def write_nodepad_snapshot(
    path: Path,
    report: WeeklyReport,
    ideas: Sequence[IdeaCard],
    clusters: Sequence[TopicCluster],
) -> Path:
    """Write a Nodepad-compatible snapshot to disk."""
    payload = report_to_nodepad_snapshot(report, ideas, clusters)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def serialize_nodepad_snapshot(
    report: WeeklyReport,
    ideas: Sequence[IdeaCard],
    clusters: Sequence[TopicCluster],
) -> str:
    """Return the Nodepad snapshot as JSON text."""
    payload = report_to_nodepad_snapshot(report, ideas, clusters)
    return json.dumps(payload, ensure_ascii=False, indent=2)
