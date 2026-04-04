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
except ModuleNotFoundError:  # pragma: no cover
    from tools.nepal_market_lib import (
        infer_channel,
        infer_city,
        infer_segment,
        normalize_whitespace,
        source_from_url,
    )

if find_spec("loguru"):
    from loguru import logger
else:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)

SignalType = Literal["icp", "competitor", "channel", "lead_source", "open_question"]
SEARCH_TIMEOUT_SECONDS = 20


class SearchResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = ""
    body: str = ""
    href: str = ""


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
    if position <= 3:
        return 0.8
    if position <= 6:
        return 0.65
    return 0.5


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
        confidence=confidence_for_rank(position),
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


def _search_sync(query: str, max_results: int) -> list[SearchResult]:
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
        )
        for item in payload
    ]


async def search_text_results(query: str, max_results: int) -> list[SearchResult]:
    logger.info(f"web_search.query query={query!r} max_results={max_results}")
    search_task = asyncio.create_task(asyncio.to_thread(_search_sync, query, max_results))
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
) -> list[dict[str, Any]]:
    results = await search_text_results(query, max_results=max_results)
    signals = [
        build_signal(result, signal_type=signal_type, city=city, position=position)
        for position, result in enumerate(results, start=1)
    ]
    return dedupe_raw_signals(signals)
