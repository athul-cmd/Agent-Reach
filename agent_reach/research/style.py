# -*- coding: utf-8 -*-
"""Style profile generation helpers."""

from __future__ import annotations

from collections import Counter
import re
from typing import Iterable, List

from agent_reach.research.models import ResearchProfile, StyleProfile, UserFeedbackEvent, WritingSample
from agent_reach.research.openai_client import OpenAIResearchClient

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


def _top_terms(texts: Iterable[str], limit: int = 10) -> List[str]:
    counter = Counter()
    for text in texts:
        counter.update(_tokenize(text))
    return [term for term, _count in counter.most_common(limit)]


def _detect_tone(text: str) -> str:
    question_ratio = text.count("?") / max(len(text), 1)
    first_person = len(re.findall(r"\b(i|my|me|we|our)\b", text.lower()))
    if question_ratio > 0.01:
        return "inquisitive"
    if first_person >= 8:
        return "reflective"
    return "analytical"


def _detect_structure_patterns(texts: Iterable[str]) -> List[str]:
    joined = "\n".join(texts)
    patterns = []
    if re.search(r"^\s*[-*]\s+", joined, re.M):
        patterns.append("bullet-heavy")
    if re.search(r"^\s*\d+\.\s+", joined, re.M):
        patterns.append("numbered-steps")
    if not patterns:
        patterns.append("paragraph-led")
    return patterns


def _feedback_topics(feedback_events: Iterable[UserFeedbackEvent], event_type: str) -> List[str]:
    texts = []
    for event in feedback_events:
        if event.event_type == event_type:
            payload = event.event_payload or {}
            texts.extend(str(v) for v in payload.values() if isinstance(v, str))
    return _top_terms(texts, limit=8)


def _openai_style_profile(
    client: OpenAIResearchClient,
    profile: ResearchProfile,
    samples: List[WritingSample],
    feedback_events: List[UserFeedbackEvent],
) -> StyleProfile:
    system_prompt = (
        "You extract a compact writing style profile for a single author. "
        "Return JSON with keys tone_markers, hook_patterns, structure_patterns, "
        "preferred_topics, avoided_topics, evidence_preferences, raw_summary."
    )
    sample_text = "\n\n".join(sample.raw_text[:2000] for sample in samples[:8])
    feedback_text = "\n".join(
        f"{event.event_type}: {event.event_payload}" for event in feedback_events[-20:]
    )
    user_prompt = (
        f"Persona brief: {profile.persona_brief}\n"
        f"Niche: {profile.niche_definition}\n"
        f"Must-track topics: {profile.must_track_topics}\n"
        f"Excluded topics: {profile.excluded_topics}\n"
        f"Audience: {profile.target_audience}\n\n"
        f"Writing samples:\n{sample_text}\n\n"
        f"Feedback:\n{feedback_text}\n"
    )
    data = client.chat_json(system_prompt, user_prompt)
    return StyleProfile(
        research_profile_id=profile.id,
        tone_markers=list(data.get("tone_markers", [])),
        hook_patterns=list(data.get("hook_patterns", [])),
        structure_patterns=list(data.get("structure_patterns", [])),
        preferred_topics=list(data.get("preferred_topics", [])),
        avoided_topics=list(data.get("avoided_topics", [])),
        evidence_preferences=list(data.get("evidence_preferences", [])),
        raw_summary=str(data.get("raw_summary", "")),
        embedding_version="openai-v1",
    )


def build_style_profile(
    profile: ResearchProfile,
    samples: List[WritingSample],
    feedback_events: List[UserFeedbackEvent],
    openai_client: OpenAIResearchClient | None = None,
) -> StyleProfile:
    """Build a style profile from samples and feedback."""
    if openai_client and openai_client.available and samples:
        try:
            return _openai_style_profile(openai_client, profile, samples, feedback_events)
        except Exception:
            pass

    sample_texts = [sample.raw_text for sample in samples if sample.raw_text.strip()]
    joined = "\n".join(sample_texts)
    preferred_topics = list(dict.fromkeys(profile.must_track_topics + _top_terms(sample_texts, 12)))
    avoided_topics = list(
        dict.fromkeys(profile.excluded_topics + _feedback_topics(feedback_events, "discard"))
    )
    hook_patterns = []
    for sample in sample_texts[:6]:
        first_line = next((line.strip() for line in sample.splitlines() if line.strip()), "")
        if first_line:
            hook_patterns.append(" ".join(first_line.split()[:8]))
    if not hook_patterns:
        hook_patterns = ["direct framing"]

    evidence_preferences = ["evidence-backed", "public-signal-aware"]
    if re.search(r"\baccording to\b|\bdata\b|\bresearch\b", joined.lower()):
        evidence_preferences.append("cites supporting data")

    return StyleProfile(
        research_profile_id=profile.id,
        tone_markers=[_detect_tone(joined)] if joined else ["analytical"],
        hook_patterns=hook_patterns[:6],
        structure_patterns=_detect_structure_patterns(sample_texts) if sample_texts else ["paragraph-led"],
        preferred_topics=preferred_topics[:16],
        avoided_topics=avoided_topics[:12],
        evidence_preferences=evidence_preferences,
        raw_summary=(
            f"Derived from {len(samples)} writing samples and {len(feedback_events)} feedback events."
        ),
    )
