# -*- coding: utf-8 -*-
"""Tests for research scoring logic."""

from datetime import timedelta

from agent_reach.research.models import ResearchProfile, SourceItem, StyleProfile, TopicCluster, utc_now
from agent_reach.research.scoring import ScoreComponents, build_cluster_score, compute_final_score


def test_compute_final_score_matches_spec_formula():
    components = ScoreComponents(
        engagement=0.5,
        niche_fit=0.9,
        novelty=0.4,
        cross_source_confirmation=0.8,
        style_alignment=0.6,
    )
    score = compute_final_score(components)
    expected = 0.30 * 0.5 + 0.30 * 0.9 + 0.15 * 0.4 + 0.15 * 0.8 + 0.10 * 0.6
    assert score == round(expected, 6)


def test_build_cluster_score_rewards_cross_source_confirmation():
    profile = ResearchProfile(
        name="AI writer",
        persona_brief="Analytical operator",
        niche_definition="AI content strategy",
        must_track_topics=["AI agents", "content strategy"],
        excluded_topics=["cryptocurrency"],
        target_audience="operators",
        desired_formats=["linkedin"],
    )
    style = StyleProfile(
        research_profile_id=profile.id,
        preferred_topics=["AI agents", "content strategy"],
        avoided_topics=["cryptocurrency"],
        hook_patterns=["What changed this week"],
        structure_patterns=["paragraph-led"],
        tone_markers=["analytical"],
    )
    now = utc_now()
    item_one = SourceItem(
        research_profile_id=profile.id,
        source="reddit",
        external_id="r1",
        canonical_url="https://reddit.com/r/1",
        author_name="user1",
        published_at=now,
        title="AI agents are changing content strategy",
        body_text="Operators discuss AI agent workflows in content systems.",
        engagement={"score": 120, "comments": 22},
    )
    item_two = SourceItem(
        research_profile_id=profile.id,
        source="youtube",
        external_id="y1",
        canonical_url="https://youtube.com/watch?v=1",
        author_name="channel1",
        published_at=now - timedelta(hours=1),
        title="YouTube creators explain AI content strategy",
        body_text="A tutorial about using AI agents for content operations.",
        engagement={"views": 15000, "comments": 120},
    )
    cluster = TopicCluster(
        research_profile_id=profile.id,
        cluster_label="AI Agents",
        cluster_summary="AI agents are repeatedly appearing in content strategy workflows.",
        representative_terms=["ai", "agents", "content", "strategy"],
        supporting_item_ids=[item_one.id, item_two.id],
        source_family_count=2,
        freshness_score=1.0,
        cluster_key="ai-agents",
    )

    components = build_cluster_score(
        profile=profile,
        style_profile=style,
        cluster=cluster,
        items=[item_one, item_two],
        recent_idea_texts=["legacy analytics workflow"],
    )

    assert components.cross_source_confirmation > 0.4
    assert components.niche_fit > 0.1
    assert compute_final_score(components) > 0
