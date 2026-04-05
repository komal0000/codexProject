from __future__ import annotations

import asyncio
import os
import time
from importlib.util import find_spec
from typing import Any

try:
    from env_loader import load_env_file
except ModuleNotFoundError:  # pragma: no cover
    from tools.env_loader import load_env_file

if find_spec("loguru"):
    from loguru import logger
else:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)

load_env_file()

TAVILY_SEARCH_DEPTH_BASIC = "basic"
TAVILY_SEARCH_DEPTH_ADVANCED = "advanced"
DEFAULT_TAVILY_COUNTRY = "nepal"
DEFAULT_MAX_RESULTS = 5


class TavilySearchResult:
    """Lightweight container for a single Tavily search result."""

    __slots__ = ("title", "url", "content", "raw_content", "score")

    def __init__(
        self,
        title: str,
        url: str,
        content: str,
        raw_content: str,
        score: float,
    ) -> None:
        self.title = title
        self.url = url
        self.content = content
        self.raw_content = raw_content
        self.score = score


class TavilySearchClient:
    """Async wrapper around the Tavily Python SDK (which is synchronous)."""

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _client(self) -> Any:
        if find_spec("tavily") is None:
            raise ImportError(
                "tavily-python is not installed. "
                "Run: pip install tavily-python>=0.5.0"
            )
        from tavily import TavilyClient  # type: ignore[import-untyped]

        return TavilyClient(api_key=self.api_key)

    def _search_sync(
        self,
        query: str,
        *,
        max_results: int,
        search_depth: str,
        country: str,
        include_raw_content: bool,
        include_domains: list[str],
        exclude_domains: list[str],
    ) -> list[TavilySearchResult]:
        client = self._client()
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_raw_content": include_raw_content,
        }
        if country:
            kwargs["country"] = country
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains

        response = client.search(**kwargs)
        results: list[TavilySearchResult] = []
        for item in response.get("results", []):
            results.append(
                TavilySearchResult(
                    title=str(item.get("title", "") or ""),
                    url=str(item.get("url", "") or ""),
                    content=str(item.get("content", "") or ""),
                    raw_content=str(item.get("raw_content", "") or ""),
                    score=float(item.get("score", 0.5)),
                )
            )
        return results

    async def search(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS,
        search_depth: str = TAVILY_SEARCH_DEPTH_BASIC,
        country: str = DEFAULT_TAVILY_COUNTRY,
        include_raw_content: bool = False,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        timeout_seconds: float = 12.0,
    ) -> list[TavilySearchResult]:
        if not self.enabled:
            logger.info("tavily.disabled reason=no_api_key")
            return []

        started_at = time.perf_counter()
        logger.info(
            f"tavily.search_started query={query!r} depth={search_depth!r} "
            f"country={country!r} max_results={max_results}"
        )
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    self._search_sync,
                    query,
                    max_results=max_results,
                    search_depth=search_depth,
                    country=country,
                    include_raw_content=include_raw_content,
                    include_domains=include_domains or [],
                    exclude_domains=exclude_domains or [],
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.warning(
                f"tavily.search_timeout query={query!r} duration_ms={duration_ms}"
            )
            return []
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.warning(
                f"tavily.search_failed query={query!r} duration_ms={duration_ms} error={exc!s}"
            )
            return []

        duration_ms = round((time.perf_counter() - started_at) * 1000)
        logger.info(
            f"tavily.search_succeeded query={query!r} result_count={len(results)} "
            f"duration_ms={duration_ms}"
        )
        return results
