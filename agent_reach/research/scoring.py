# -*- coding: utf-8 -*-
"""Ranking logic for research clusters and idea candidates."""

from __future__ import annotations

from dataclasses import dataclass
from math import log10
import re
from typing import Iterable, Sequence

from agent_reach.research.models import ResearchProfile, SourceItem, StyleProfile, TopicCluster

_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "have",
    "your",
    "about",
    "into",
    "they",
    "their",
    "what",
    "when",
    "where",
    "which",
    "will",
    "would",
    "there",
    "them",
    "just",
    "than",
    "also",
    "could",
    "should",
    "while",
    "because",
    "then",
    "more",
    "been",
}


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_\-]+", text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    intersection = left_set & right_set
    union = left_set | right_set
    return len(intersection) / len(union)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(slots=True)
class ScoreComponents:
    """Atomic score values used in final ranking."""

    engagement: float
    niche_fit: float
    novelty: float
    cross_source_confirmation: float
    style_alignment: float

    def as_dict(self) -> dict[str, float]:
        return {
            "engagement": round(self.engagement, 4),
            "niche_fit": round(self.niche_fit, 4),
            "novelty": round(self.novelty, 4),
            "cross_source_confirmation": round(self.cross_source_confirmation, 4),
            "style_alignment": round(self.style_alignment, 4),
        }


def compute_final_score(components: ScoreComponents) -> float:
    """Compute the fixed weighted score from the source-of-truth spec."""
    score = (
        0.30 * components.engagement
        + 0.30 * components.niche_fit
        + 0.15 * components.novelty
        + 0.15 * components.cross_source_confirmation
        + 0.10 * components.style_alignment
    )
    return round(score, 6)


def normalize_engagement(item: SourceItem) -> float:
    """Normalize heterogeneous public metrics into a 0-1 range."""
    numeric_values = []
    for value in item.engagement.values():
        if isinstance(value, (int, float)) and value >= 0:
            numeric_values.append(float(value))
    if not numeric_values:
        return 0.0
    raw_score = sum(log10(v + 1.0) for v in numeric_values)
    return _clamp(raw_score / 10.0)


def compute_niche_fit(profile: ResearchProfile, text: str) -> float:
    """Measure overlap with must-track and excluded terms."""
    text_tokens = _tokenize(text)
    if not text_tokens:
        return 0.0
    must_tokens = _tokenize(" ".join(profile.must_track_topics + [profile.niche_definition]))
    excluded_tokens = _tokenize(" ".join(profile.excluded_topics))
    overlap = _jaccard(text_tokens, must_tokens) if must_tokens else 0.15
    excluded_overlap = _jaccard(text_tokens, excluded_tokens) if excluded_tokens else 0.0
    return _clamp(overlap - 0.6 * excluded_overlap)


def compute_novelty(text: str, recent_texts: Sequence[str]) -> float:
    """Reward ideas that are not semantic duplicates of recent items."""
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    if not recent_texts:
        return 1.0
    max_similarity = max((_jaccard(tokens, _tokenize(t)) for t in recent_texts), default=0.0)
    return _clamp(1.0 - max_similarity)


def compute_cross_source_confirmation(cluster: TopicCluster, items: Sequence[SourceItem]) -> float:
    """Reward clusters represented across source families."""
    item_ids = set(cluster.supporting_item_ids)
    sources = {item.source for item in items if item.id in item_ids}
    return _clamp(len(sources) / 4.0)


def compute_style_alignment(style_profile: StyleProfile | None, text: str) -> float:
    """Estimate how well a text fits the learned style profile."""
    if style_profile is None:
        return 0.15
    text_tokens = _tokenize(text)
    preferred = _tokenize(" ".join(style_profile.preferred_topics + style_profile.hook_patterns))
    avoided = _tokenize(" ".join(style_profile.avoided_topics))
    preferred_overlap = _jaccard(text_tokens, preferred) if preferred else 0.2
    avoided_overlap = _jaccard(text_tokens, avoided) if avoided else 0.0
    return _clamp(preferred_overlap - 0.5 * avoided_overlap + 0.2)


def build_cluster_score(
    profile: ResearchProfile,
    style_profile: StyleProfile | None,
    cluster: TopicCluster,
    items: Sequence[SourceItem],
    recent_idea_texts: Sequence[str],
) -> ScoreComponents:
    """Build weighted score components for a cluster."""
    cluster_items = [item for item in items if item.id in set(cluster.supporting_item_ids)]
    engagement = (
        sum(normalize_engagement(item) for item in cluster_items) / max(len(cluster_items), 1)
    )
    cluster_text = f"{cluster.cluster_label}\n{cluster.cluster_summary}\n{' '.join(cluster.representative_terms)}"
    niche_fit = compute_niche_fit(profile, cluster_text)
    novelty = compute_novelty(cluster_text, recent_idea_texts)
    cross_source_confirmation = compute_cross_source_confirmation(cluster, cluster_items)
    style_alignment = compute_style_alignment(style_profile, cluster_text)
    return ScoreComponents(
        engagement=engagement,
        niche_fit=niche_fit,
        novelty=novelty,
        cross_source_confirmation=cross_source_confirmation,
        style_alignment=style_alignment,
    )
