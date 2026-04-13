# -*- coding: utf-8 -*-
"""Topic clustering helpers for source items."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import re
from typing import Iterable, List

from agent_reach.research.models import ResearchProfile, SourceItem, TopicCluster

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


def _tokenize(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_\-]+", text.lower())
        if token not in _STOPWORDS and len(token) > 2
    ]


def _primary_cluster_key(profile: ResearchProfile, item: SourceItem) -> str:
    text_tokens = _tokenize(item.combined_text())
    for topic in profile.must_track_topics:
        topic_tokens = _tokenize(topic)
        if set(topic_tokens) & set(text_tokens):
            return " ".join(topic_tokens) if topic_tokens else topic.lower()
    if text_tokens:
        return text_tokens[0]
    return "uncategorized"


def _summarize_terms(texts: Iterable[str], limit: int = 6) -> List[str]:
    counter = Counter()
    for text in texts:
        counter.update(_tokenize(text))
    return [term for term, _count in counter.most_common(limit)]


def _freshness_score(items: List[SourceItem]) -> float:
    if not items:
        return 0.0
    latest = max(item.published_at for item in items)
    age_days = max((datetime.now(timezone.utc) - latest).days, 0)
    return max(0.0, min(1.0, 1.0 - (age_days / 30.0)))


def cluster_source_items(profile: ResearchProfile, items: List[SourceItem]) -> List[TopicCluster]:
    """Group collected source items into simple lexical clusters."""
    grouped: dict[str, list[SourceItem]] = defaultdict(list)
    for item in items:
        grouped[_primary_cluster_key(profile, item)].append(item)

    clusters = []
    for key, group in grouped.items():
        terms = _summarize_terms([item.combined_text() for item in group])
        label = key.replace("-", " ").strip().title() or "Emerging Theme"
        summary = " | ".join(
            filter(None, [group[0].title if group else "", " / ".join(terms[:4])])
        )
        cluster_hash = hashlib.sha1(
            f"{profile.id}:{key}:{','.join(sorted(item.id for item in group))}".encode("utf-8")
        ).hexdigest()[:16]
        clusters.append(
            TopicCluster(
                research_profile_id=profile.id,
                cluster_label=label,
                cluster_summary=summary[:400],
                representative_terms=terms,
                supporting_item_ids=[item.id for item in group],
                source_family_count=len({item.source for item in group}),
                freshness_score=_freshness_score(group),
                cluster_key=f"{key}:{cluster_hash}",
            )
        )
    return clusters
