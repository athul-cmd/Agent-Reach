# -*- coding: utf-8 -*-
"""Tests for Nodepad snapshot export."""

from datetime import timedelta

from agent_reach.research.models import IdeaCard, TopicCluster, WeeklyReport, utc_now
from agent_reach.research.snapshot import report_to_nodepad_snapshot


def test_report_to_nodepad_snapshot_has_root_and_deduped_clusters():
    now = utc_now()
    cluster = TopicCluster(
        research_profile_id="profile_1",
        cluster_label="AI Agents",
        cluster_summary="Repeated discussion around AI agents.",
        representative_terms=["ai", "agents"],
        supporting_item_ids=["item1", "item2"],
        source_family_count=2,
        freshness_score=1.0,
        cluster_key="ai-agents",
        id="cluster_1",
        final_score=0.8,
    )
    idea_one = IdeaCard(
        research_profile_id="profile_1",
        topic_cluster_id=cluster.id,
        headline="Idea one",
        hook="Hook one",
        why_now="Why now one",
        outline_md="- point",
        evidence_item_ids=["item1"],
        final_score=0.9,
        id="idea_1",
    )
    idea_two = IdeaCard(
        research_profile_id="profile_1",
        topic_cluster_id=cluster.id,
        headline="Idea two",
        hook="Hook two",
        why_now="Why now two",
        outline_md="- point",
        evidence_item_ids=["item2"],
        final_score=0.85,
        id="idea_2",
    )
    report = WeeklyReport(
        research_profile_id="profile_1",
        report_period_start=now - timedelta(days=7),
        report_period_end=now,
        top_idea_ids=[idea_one.id, idea_two.id],
        top_creator_ids=[],
        summary_md="## Weekly Digest",
        id="report_1",
    )

    snapshot = report_to_nodepad_snapshot(report, [idea_one, idea_two], [cluster])

    assert snapshot["version"] == 2
    blocks = snapshot["project"]["blocks"]
    assert any(block["contentType"] == "thesis" for block in blocks)
    cluster_blocks = [block for block in blocks if block["id"] == "cluster-cluster_1"]
    assert len(cluster_blocks) == 1
