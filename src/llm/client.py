from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from config import load_settings


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
JSON_INLINE_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


@dataclass
class LLMClient:
    client: OpenAI
    model: str
    timeout: int

    @classmethod
    def from_env(cls) -> "LLMClient":
        settings = load_settings(require_llm_api_key=True)
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_api_base, timeout=settings.llm_timeout)
        return cls(client=client, model=settings.llm_model, timeout=settings.llm_timeout)

    def complete(self, prompt: str, **kwargs: Any) -> str | dict[str, Any] | list[Any]:
        return self.chat_completion(messages=[{"role": "user", "content": prompt}], **kwargs)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        json_mode: bool = False,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> str | dict[str, Any] | list[Any]:
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                response_format = {"type": "json_object"} if json_mode else None
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                    **kwargs,
                )
                content = response.choices[0].message.content or ""
                if json_mode:
                    return self._extract_json(content)
                return content
            except Exception as exc:  # pragma: no cover
                last_error = exc
                status_code = getattr(exc, "status_code", None)
                should_retry = status_code in (429, 500, 502, 503, 504) or "timeout" in str(exc).lower()
                if attempt == max_retries - 1 or not should_retry:
                    raise
                time.sleep(2**attempt)
        if last_error:
            raise last_error
        raise RuntimeError("chat_completion failed without exception")

    def smoke_test(self) -> bool:
        result = self.chat_completion(messages=[{"role": "user", "content": "reply with pong"}], temperature=0.0)
        return isinstance(result, str) and "pong" in result.lower()

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any] | list[Any]:
        text = content.strip()
        for candidate in (text, *(m.group(1) for m in JSON_BLOCK_RE.finditer(text))):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        match = JSON_INLINE_RE.search(text)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"No JSON object found in response: {content[:300]}")
