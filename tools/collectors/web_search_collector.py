from __future__ import annotations

import asyncio
from importlib.util import find_spec
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

try:
    from nepal_market_lib import (
        infer_channel,
        infer_city,
        infer_segment,
        normalize_whitespace,
        source_from_url,
    )
    from tavily_client import TavilySearchClient, TavilySearchResult
except ModuleNotFoundError:  # pragma: no cover
    from tools.nepal_market_lib import (
        infer_channel,
        infer_city,
        infer_segment,
        normalize_whitespace,
        source_from_url,
    )
    from tools.tavily_client import TavilySearchClient, TavilySearchResult

if find_spec("loguru"):
    from loguru import logger
else:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)

SignalType = Literal["icp", "competitor", "channel", "lead_source", "open_question"]
SEARCH_TIMEOUT_SECONDS = 8
TAVILY_SEARCH_TIMEOUT_SECONDS = 12.0


class SearchResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = ""
    body: str = ""
    href: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_content: str = ""


class RawSignal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str
    subject: str
    signal_type: SignalType
    segment: str = ""
    city: str = ""
    channel: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str
    url: str = ""


def confidence_for_rank(position: int) -> float:
    """Fallback confidence when no relevance score is available (DuckDuckGo path)."""
    if position <= 3:
        return 0.8
    if position <= 6:
        return 0.65
    return 0.5


def confidence_from_score(score: float, position: int) -> float:
    """Map Tavily relevance score (0-1) to confidence, using position as tiebreaker floor."""
    clamped = max(0.0, min(1.0, score))
    if clamped > 0.0:
        return round(clamped, 2)
    return confidence_for_rank(position)


def ensure_search_dependency() -> bool:
    if find_spec("ddgs") is None and find_spec("duckduckgo_search") is None:
        logger.warning("No DDG search package is installed; live web search collector disabled.")
        return False
    return True


def extract_subject(result: SearchResult) -> str:
    title = normalize_whitespace(result.title)
    if title:
        return title
    body = normalize_whitespace(result.body)
    if not body:
        return "Untitled result"
    return body.split(".")[0][:120].strip() or "Untitled result"


def build_signal(
    result: SearchResult,
    signal_type: SignalType,
    city: str,
    position: int,
    segment_hint: str | None = None,
    channel_hint: str | None = None,
    subject_override: str | None = None,
) -> RawSignal:
    snippet = normalize_whitespace(result.body)
    subject = normalize_whitespace(subject_override) or extract_subject(result)
    combined_text = " ".join(
        part for part in (result.title, result.body, subject, segment_hint, channel_hint) if part
    )
    normalized_city = normalize_whitespace(city) or infer_city(combined_text)
    url = normalize_whitespace(result.href)
    parsed = urlparse(url)
    source = source_from_url(url) if url else normalize_whitespace(parsed.netloc) or "duckduckgo"
    return RawSignal(
        source=source,
        subject=subject,
        signal_type=signal_type,
        segment=normalize_whitespace(segment_hint) or infer_segment(combined_text),
        city=normalized_city,
        channel=normalize_whitespace(channel_hint) or infer_channel(combined_text),
        confidence=confidence_from_score(result.score, position),
        notes=snippet or "Search result returned without a snippet.",
        url=url,
    )


def dedupe_raw_signals(signals: list[RawSignal]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for signal in signals:
        key = (signal.signal_type, signal.subject.lower(), signal.url.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal.model_dump())
    return deduped


def _tavily_to_search_results(tavily_results: list[TavilySearchResult]) -> list[SearchResult]:
    """Convert Tavily result objects to the shared SearchResult model."""
    converted: list[SearchResult] = []
    for item in tavily_results:
        body = normalize_whitespace(item.content) or normalize_whitespace(item.raw_content)[:600]
        converted.append(
            SearchResult(
                title=normalize_whitespace(item.title),
                body=body,
                href=normalize_whitespace(item.url),
                score=round(max(0.0, min(1.0, item.score)), 2),
                raw_content=normalize_whitespace(item.raw_content)[:1600],
            )
        )
    return converted


async def search_text_results_tavily(
    query: str,
    max_results: int,
    *,
    search_depth: str = "basic",
    country: str = "nepal",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    include_raw_content: bool = False,
) -> list[SearchResult]:
    """Search via Tavily. Returns empty list if Tavily is not configured."""
    client = TavilySearchClient()
    if not client.enabled:
        return []
    tavily_results = await client.search(
        query,
        max_results=max_results,
        search_depth=search_depth,
        country=country,
        include_raw_content=include_raw_content,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        timeout_seconds=TAVILY_SEARCH_TIMEOUT_SECONDS,
    )
    return _tavily_to_search_results(tavily_results)


def _search_sync_ddg(query: str, max_results: int) -> list[SearchResult]:
    if not ensure_search_dependency():
        return []
    if find_spec("ddgs") is not None:
        from ddgs import DDGS
    else:
        from duckduckgo_search import DDGS

    try:
        ddgs_client = DDGS(timeout=SEARCH_TIMEOUT_SECONDS)
    except TypeError:
        ddgs_client = DDGS()

    with ddgs_client as ddgs:
        payload = list(ddgs.text(query, max_results=max_results))
    return [
        SearchResult(
            title=item.get("title", ""),
            body=item.get("body", ""),
            href=item.get("href", ""),
            score=0.0,
        )
        for item in payload
    ]


async def search_text_results(
    query: str,
    max_results: int,
    *,
    search_depth: str = "basic",
    country: str = "nepal",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    include_raw_content: bool = False,
) -> list[SearchResult]:
    """Primary search: tries Tavily first, falls back to DuckDuckGo."""
    tavily_results = await search_text_results_tavily(
        query,
        max_results,
        search_depth=search_depth,
        country=country,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        include_raw_content=include_raw_content,
    )
    if tavily_results:
        logger.info(f"web_search.backend backend=tavily query={query!r} result_count={len(tavily_results)}")
        return tavily_results

    logger.info(f"web_search.backend backend=duckduckgo query={query!r} max_results={max_results}")
    search_task = asyncio.create_task(asyncio.to_thread(_search_sync_ddg, query, max_results))
    try:
        done, _ = await asyncio.wait({search_task}, timeout=SEARCH_TIMEOUT_SECONDS)
        if not done:
            search_task.cancel()
            raise asyncio.TimeoutError
        return search_task.result()
    except asyncio.TimeoutError:
        logger.warning(f"web_search.timeout query={query!r} timeout_seconds={SEARCH_TIMEOUT_SECONDS}")
    except httpx.HTTPError as exc:
        logger.warning(f"web_search.http_error query={query!r} error={exc!s}")
    except Exception as exc:  # pragma: no cover
        logger.warning(f"web_search.failed query={query!r} error={exc!s}")
    return []


async def collect_from_web_search(
    query: str,
    signal_type: SignalType,
    city: str = "Kathmandu",
    max_results: int = 10,
    *,
    search_depth: str = "basic",
    exclude_domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    results = await search_text_results(
        query,
        max_results=max_results,
        search_depth=search_depth,
        country="nepal",
        exclude_domains=exclude_domains,
    )
    signals = [
        build_signal(result, signal_type=signal_type, city=city, position=position)
        for position, result in enumerate(results, start=1)
    ]
    return dedupe_raw_signals(signals)
