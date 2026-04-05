from __future__ import annotations

import json
import os
import time
from importlib.util import find_spec
from typing import Any

import httpx

try:
    from env_loader import load_env_file
except ModuleNotFoundError:  # pragma: no cover
    from tools.env_loader import load_env_file

if find_spec("loguru"):
    from loguru import logger
else:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
load_env_file()
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
DEFAULT_TIMEOUT_SECONDS = 20.0


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or DEFAULT_OPENROUTER_MODEL
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            logger.info(f"openrouter.disabled model={self.model!r}")
            return None

        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "Nepal Market Research API"),
        }

        logger.info(f"openrouter.request_started model={self.model!r}")
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.warning(
                f"openrouter.request_failed model={self.model!r} duration_ms={duration_ms} error={exc!s}"
            )
            return None

        content = self._extract_content(response.json())
        if not content:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.warning(f"openrouter.empty_response model={self.model!r} duration_ms={duration_ms}")
            return None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.warning(
                f"openrouter.invalid_json model={self.model!r} duration_ms={duration_ms} "
                f"content_preview={content[:160]!r}"
            )
            return None
        duration_ms = round((time.perf_counter() - started_at) * 1000)
        logger.info(f"openrouter.request_succeeded model={self.model!r} duration_ms={duration_ms}")
        return parsed

    def _extract_content(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "".join(text_parts)
        return ""
