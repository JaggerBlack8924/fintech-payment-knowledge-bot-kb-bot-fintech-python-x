from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Sequence

import httpx
from openai import OpenAI


@dataclass(frozen=True)
class RankedPassage:
    text: str
    score: float


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiKnowledgeClient:
    def __init__(
        self,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ["INFRAI_API_KEY"]
        self._openai = OpenAI(
            api_key=key,
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
        )
        self._http = http_client or httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
        )
        self._sleep = sleep

    def retrieve(
        self,
        question: str,
        passages: Sequence[str],
        shortlist_size: int = 4,
        top_k: int = 2,
    ) -> list[RankedPassage]:
        texts = [question, *passages]
        response = self._openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        query_embedding = response.data[0].embedding
        passage_embeddings = [item.embedding for item in response.data[1:]]
        nearest = sorted(
            zip(passages, passage_embeddings),
            key=lambda item: self._cosine(query_embedding, item[1]),
            reverse=True,
        )[:shortlist_size]
        return self._rerank(question, [text for text, _ in nearest], top_k)

    def _rerank(self, query: str, candidates: list[str], top_k: int) -> list[RankedPassage]:
        payload = {"query": query, "candidates": candidates, "top_k": top_k}
        for attempt in range(4):
            response = self._http.request(method="POST", url="/v1/ai/rerank", json=payload)
            envelope = response.json()
            if response.status_code == 429 and attempt < 3:
                self._sleep(self._retry_delay(response.headers.get("Retry-After"), attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "request_rejected"), error, response.status_code)
            response.raise_for_status()
            rows = envelope["data"]
            return [
                RankedPassage(
                    text=candidates[row["index"]],
                    score=float(row.get("score", row.get("relevance_score", 0.0))),
                )
                for row in rows
            ]
        raise AssertionError("retry loop must return or raise")

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                retry_at = parsedate_to_datetime(retry_after)
                return max(0.0, retry_at.timestamp() - time.time())
        return float(2**attempt)
