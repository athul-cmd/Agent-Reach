# -*- coding: utf-8 -*-
"""Small OpenAI client wrapper used by the research worker."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests


class OpenAIResearchClient:
    """Lightweight OpenAI API wrapper."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        chat_model: str = "gpt-4.1-mini",
        embedding_model: str = "text-embedding-3-small",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.timeout = timeout

    @property
    def available(self) -> bool:
        """Return whether the client is configured."""
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for a list of texts."""
        if not self.available or not texts:
            return []
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers=self._headers(),
            json={"model": self.embedding_model, "input": texts},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data.get("data", [])]

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Request a JSON object from the chat completions endpoint."""
        if not self.available:
            raise RuntimeError("OpenAI client is not configured")
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": model or self.chat_model,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return json.loads(content)
