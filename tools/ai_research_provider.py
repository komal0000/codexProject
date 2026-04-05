from __future__ import annotations

import asyncio
import json
import re
from importlib.util import find_spec
from typing import Any, Awaitable, Callable, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

try:
    from openrouter_client import OpenRouterClient
    from tavily_client import TavilySearchClient
    from nepal_market_lib import (
        infer_city,
        infer_segment,
        normalize_signal,
        normalize_whitespace,
        source_from_url,
    )
    from collectors.web_search_collector import SearchResult, build_signal, search_text_results
except ModuleNotFoundError:  # pragma: no cover
    from tools.openrouter_client import OpenRouterClient
    from tools.tavily_client import TavilySearchClient
    from tools.nepal_market_lib import (
        infer_city,
        infer_segment,
        normalize_signal,
        normalize_whitespace,
        source_from_url,
    )
    from tools.collectors.web_search_collector import SearchResult, build_signal, search_text_results

if find_spec("loguru"):
    from loguru import logger
else:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)

ResearchMode = Literal["fast_draft", "free_first", "grounded_paid"]
SignalType = Literal["icp", "competitor", "channel", "lead_source", "open_question"]
MAX_TASKS = 4
MAX_RESULTS_PER_QUERY = 3
MAX_PAGES_PER_QUERY = 2
FETCH_TIMEOUT_SECONDS = 6.0

MODE_TO_SEARCH_DEPTH: dict[str, str] = {
    "fast_draft": "basic",
    "free_first": "basic",
    "grounded_paid": "advanced",
}


class SearchTask(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str
    signal_type: SignalType
    city: str = "Urban Nepal"
    segment_hint: str = ""
    channel_hint: str = ""
    competitor_label: str = ""


class SourcePage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str
    signal_type: SignalType
    title: str
    snippet: str
    url: str
    source: str
    city: str = ""
    segment_hint: str = ""
    channel_hint: str = ""
    competitor_label: str = ""
    fetched_excerpt: str = ""


class ResearchProviderResult(BaseModel):
    mode: ResearchMode
    signals: list[dict[str, Any]]
    source_pages: list[dict[str, str]]
    citations_count: int = Field(ge=0)


def extract_city_hint(text: str) -> str:
    normalized_text = normalize_whitespace(text)
    in_match = re.search(r"\bin\s+([a-zA-Z][a-zA-Z\s-]{1,40})", normalized_text, re.IGNORECASE)
    if in_match:
        candidate = normalize_whitespace(in_match.group(1)).split(" for ")[0].split(" with ")[0].strip(" ,.-")
        if candidate:
            return candidate.title()
    return infer_city(normalized_text)


def normalize_target_segment(target_customer: str, product_name: str) -> str:
    normalized_target = normalize_whitespace(target_customer)
    normalized_product_name = normalize_whitespace(product_name)
    if not normalized_target:
        return normalized_product_name or "businesses"

    lower_target = normalized_target.lower()
    city_hint = extract_city_hint(normalized_target)
    if "customer" in lower_target or "customers" in lower_target:
        if any(token in lower_target for token in ("shop", "shops", "store", "stores", "retail")):
            return normalize_whitespace(f"small retail shops {city_hint}")
        return normalized_product_name or "businesses"
    return normalized_target


def product_search_phrase(product_description: str, product_name: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-zA-Z]+", product_description.lower())
        if len(token) > 3 and token not in {"with", "that", "from", "into", "your", "their", "they", "host"}
    ]
    phrase = " ".join(list(dict.fromkeys(tokens))[:5])
    return normalize_whitespace(phrase or product_name or product_description).strip()


def fallback_search_tasks(brief: dict[str, Any], mode: ResearchMode) -> list[SearchTask]:
    target_segment = normalize_target_segment(
        str(brief.get("target_customer_guess", "")),
        str(brief.get("product_name", "")),
    )
    product_name = normalize_whitespace(brief.get("product_name"))
    product_description = normalize_whitespace(brief.get("product_description"))
    city = extract_city_hint(" ".join((str(brief.get("target_customer_guess", "")), product_description, target_segment)))
    product_phrase = product_search_phrase(product_description, product_name)
    tasks = [
        SearchTask(
            query=f"{target_segment} Nepal WhatsApp business demand",
            signal_type="icp",
            city=city,
            segment_hint=target_segment,
            channel_hint="WhatsApp",
        ),
        SearchTask(
            query=f"{target_segment} {city} Nepal Facebook Instagram WhatsApp",
            signal_type="channel",
            city=city,
            segment_hint=target_segment,
        ),
        SearchTask(
            query=f"{target_segment} {city} Nepal business directory retailers",
            signal_type="lead_source",
            city=city,
            segment_hint=target_segment,
        ),
    ]
    competitor_examples = [
        normalize_whitespace(item)
        for item in brief.get("competitor_examples", [])
        if normalize_whitespace(item)
    ]
    if competitor_examples:
        tasks.append(
            SearchTask(
                query=f"{competitor_examples[0]} pricing Nepal",
                signal_type="competitor",
                city="Nationwide",
                competitor_label=competitor_examples[0],
            )
        )
    elif mode != "fast_draft":
        tasks.append(
            SearchTask(
                query=f"{product_phrase} software alternatives Nepal",
                signal_type="competitor",
                city="Nationwide",
                competitor_label="",
            )
        )
    return tasks[:MAX_TASKS]


def parse_search_tasks(payload: dict[str, Any]) -> list[SearchTask]:
    raw_tasks = payload.get("queries", [])
    if not isinstance(raw_tasks, list):
        return []
    parsed: list[SearchTask] = []
    for item in raw_tasks[:MAX_TASKS]:
        if not isinstance(item, dict):
            continue
        try:
            parsed.append(SearchTask.model_validate(item))
        except ValidationError:
            continue
    return parsed


def _search_depth_for_mode(mode: ResearchMode) -> str:
    return MODE_TO_SEARCH_DEPTH.get(mode, "basic")


def _tavily_active() -> bool:
    return TavilySearchClient().enabled


async def plan_search_tasks(
    brief: dict[str, Any],
    mode: ResearchMode,
    client: OpenRouterClient | None = None,
) -> list[SearchTask]:
    fallback_tasks = fallback_search_tasks(brief, mode)
    if mode == "fast_draft":
        logger.info("provider.plan_source source=fast_draft_fallback query_count=2")
        return fallback_tasks[:2]

    openrouter = client or OpenRouterClient()
    if not openrouter.enabled:
        logger.info(f"provider.plan_source source=fallback query_count={len(fallback_tasks)} reason=no_openrouter")
        return fallback_tasks

    system_prompt = (
        "You plan focused market-research search queries. "
        "Return compact JSON only with a top-level 'queries' array. "
        "Each query item must include: query, signal_type, city, segment_hint, channel_hint, competitor_label. "
        "Allowed signal_type values: icp, competitor, channel, lead_source, open_question. "
        "Prefer 3-4 queries total and do not ask for broad generic searches."
    )
    user_prompt = json.dumps(
        {
            "brief": brief,
            "fallback_queries": [item.model_dump() for item in fallback_tasks],
            "requirements": {
                "max_queries": MAX_TASKS,
                "goal": "Find evidence for best target shops, channels, lead sources, competitors, and pricing direction in Nepal.",
            },
        },
        ensure_ascii=True,
    )
    payload = await openrouter.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    parsed_tasks = parse_search_tasks(payload or {})
    if parsed_tasks:
        logger.info(f"provider.plan_source source=model query_count={len(parsed_tasks)}")
        return parsed_tasks
    logger.info(f"provider.plan_source source=fallback query_count={len(fallback_tasks)} reason=model_empty")
    return fallback_tasks


async def fetch_page_excerpt(url: str) -> str:
    """Fetch a page excerpt via raw HTTP. Skipped when Tavily supplies raw_content."""
    if not url:
        return ""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NepalMarketResearchBot/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(f"research_provider.fetch_failed url={url!r} error={exc!s}")
        return ""

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return normalize_whitespace(response.text[:1200])
    html = response.text
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return normalize_whitespace(text)[:1600]


async def gather_source_pages(
    tasks: list[SearchTask],
    mode: ResearchMode = "free_first",
) -> list[SourcePage]:
    if not tasks:
        logger.info("provider.source_fetch query_count=0 page_count=0")
        return []

    search_depth = _search_depth_for_mode(mode)
    use_tavily = _tavily_active()
    include_raw = use_tavily and mode == "grounded_paid"

    batches = await asyncio.gather(
        *(
            search_text_results(
                task.query,
                max_results=MAX_RESULTS_PER_QUERY,
                search_depth=search_depth,
                country="nepal",
                include_raw_content=include_raw,
            )
            for task in tasks
        ),
        return_exceptions=True,
    )

    candidates: list[SourcePage] = []
    seen_urls: set[str] = set()
    for task, batch in zip(tasks, batches):
        if isinstance(batch, Exception):
            continue
        kept_for_task = 0
        for result in batch:
            url = normalize_whitespace(result.href)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                SourcePage(
                    query=task.query,
                    signal_type=task.signal_type,
                    title=normalize_whitespace(result.title) or "Untitled result",
                    snippet=normalize_whitespace(result.body),
                    url=url,
                    source=source_from_url(url),
                    city=task.city,
                    segment_hint=task.segment_hint,
                    channel_hint=task.channel_hint,
                    competitor_label=task.competitor_label,
                    fetched_excerpt=normalize_whitespace(result.raw_content)[:1600] if result.raw_content else "",
                )
            )
            kept_for_task += 1
            if kept_for_task >= MAX_PAGES_PER_QUERY:
                break

    if use_tavily:
        logger.info(
            f"provider.source_fetch backend=tavily depth={search_depth!r} "
            f"query_count={len(tasks)} page_count={len(candidates)}"
        )
        return candidates

    excerpts = await asyncio.gather(
        *(fetch_page_excerpt(page.url) for page in candidates),
        return_exceptions=True,
    )
    pages: list[SourcePage] = []
    for page, excerpt in zip(candidates, excerpts):
        if isinstance(excerpt, Exception):
            pages.append(page)
            continue
        page.fetched_excerpt = excerpt
        pages.append(page)
    logger.info(f"provider.source_fetch backend=duckduckgo query_count={len(tasks)} page_count={len(pages)}")
    return pages


def fallback_draft_signals(brief: dict[str, Any]) -> list[dict[str, Any]]:
    target_segment = normalize_target_segment(
        str(brief.get("target_customer_guess", "")),
        str(brief.get("product_name", "")),
    )
    city = extract_city_hint(
        " ".join((str(brief.get("target_customer_guess", "")), target_segment, str(brief.get("product_description", ""))))
    )
    product_name = normalize_whitespace(brief.get("product_name"))
    draft_rows = [
        {
            "source": "ai_draft",
            "subject": f"{target_segment} need faster chat response",
            "signal_type": "icp",
            "segment": infer_segment(target_segment),
            "city": city,
            "channel": "WhatsApp",
            "confidence": 0.62,
            "notes": f"AI draft hypothesis for {product_name} based on the submitted brief.",
            "url": "",
        },
        {
            "source": "ai_draft",
            "subject": "Facebook and WhatsApp seller communities",
            "signal_type": "channel",
            "segment": infer_segment(target_segment),
            "city": city,
            "channel": "Facebook",
            "confidence": 0.58,
            "notes": "AI draft recommendation for initial outreach channels.",
            "url": "",
        },
        {
            "source": "ai_draft",
            "subject": "Local retailer directories and POS vendor partnerships",
            "signal_type": "lead_source",
            "segment": infer_segment(target_segment),
            "city": city,
            "channel": "Referrals",
            "confidence": 0.55,
            "notes": "AI draft lead-source hypothesis pending verification.",
            "url": "",
        },
        {
            "source": "ai_draft",
            "subject": "Will small shops accept monthly pricing or prefer one-time setup?",
            "signal_type": "open_question",
            "segment": infer_segment(target_segment),
            "city": city,
            "channel": "Mixed",
            "confidence": 0.6,
            "notes": "Pricing sensitivity should be validated in early sales calls.",
            "url": "",
        },
    ]
    return [normalize_signal(row) for row in draft_rows]


def heuristic_signals_from_pages(pages: list[SourcePage]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        result = SearchResult(title=page.title, body=page.snippet or page.fetched_excerpt, href=page.url)
        subject_override = page.competitor_label or None
        signal = build_signal(
            result,
            signal_type=page.signal_type,
            city=page.city or infer_city(page.snippet),
            position=index,
            segment_hint=page.segment_hint,
            channel_hint=page.channel_hint,
            subject_override=subject_override,
        ).model_dump()
        signals.append(normalize_signal(signal))
    return signals


def parse_model_signals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_signals = payload.get("signals", [])
    if not isinstance(raw_signals, list):
        return []
    parsed: list[dict[str, Any]] = []
    for item in raw_signals:
        if not isinstance(item, dict):
            continue
        try:
            parsed.append(normalize_signal(item))
        except Exception:
            continue
    return parsed


async def generate_draft_signals_with_model(
    brief: dict[str, Any],
    client: OpenRouterClient | None = None,
) -> list[dict[str, Any]]:
    openrouter = client or OpenRouterClient()
    if not openrouter.enabled:
        logger.info("provider.draft_source source=fallback reason=no_openrouter")
        return []

    system_prompt = (
        "You produce concise market-research draft signals from a SaaS brief. "
        "Return JSON only with a top-level 'signals' array. "
        "Each signal must include source, subject, signal_type, segment, city, channel, confidence, notes, url. "
        "Allowed signal_type values: icp, competitor, channel, lead_source, open_question. "
        "Because this is draft mode, use source='ai_draft' and url=''."
    )
    user_prompt = json.dumps(
        {
            "brief": brief,
            "requirements": {
                "max_signals": 8,
                "goal": "Identify best target shops, likely channels, likely pricing direction, and key open questions.",
            },
        },
        ensure_ascii=True,
    )
    payload = await openrouter.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    signals = parse_model_signals(payload or {})
    if signals:
        logger.info(f"provider.draft_source source=model signal_count={len(signals)}")
        return signals
    logger.info("provider.draft_source source=fallback reason=model_empty")
    return []


async def extract_signals_with_model(
    brief: dict[str, Any],
    pages: list[SourcePage],
    client: OpenRouterClient | None = None,
) -> list[dict[str, Any]]:
    openrouter = client or OpenRouterClient()
    if not openrouter.enabled or not pages:
        reason = "no_openrouter" if not openrouter.enabled else "no_pages"
        logger.info(f"provider.extract_source source=heuristic reason={reason}")
        return []

    system_prompt = (
        "You extract structured market-research signals from provided evidence only. "
        "Return JSON only with a top-level 'signals' array. "
        "Each signal must include source, subject, signal_type, segment, city, channel, confidence, notes, url. "
        "Use only evidence from the provided pages. Preserve the real page url in every signal. "
        "Do not invent citations."
    )
    user_prompt = json.dumps(
        {
            "brief": brief,
            "pages": [page.model_dump() for page in pages],
            "requirements": {
                "max_signals": 12,
                "focus": "best initial shop segments, channels, lead sources, pricing clues, and competitors",
            },
        },
        ensure_ascii=True,
    )
    payload = await openrouter.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    signals = parse_model_signals(payload or {})
    if signals:
        logger.info(f"provider.extract_source source=model signal_count={len(signals)}")
        return signals
    logger.info("provider.extract_source source=heuristic reason=model_empty")
    return []


async def run_research_provider(
    brief: dict[str, Any],
    mode: ResearchMode = "free_first",
    client: OpenRouterClient | None = None,
    stage_callback: Callable[[str], Awaitable[None] | None] | None = None,
) -> ResearchProviderResult:
    selected_mode: ResearchMode = mode if mode in {"fast_draft", "free_first", "grounded_paid"} else "free_first"
    if selected_mode == "fast_draft":
        signals = await generate_draft_signals_with_model(brief, client=client)
        if not signals:
            signals = fallback_draft_signals(brief)
            logger.info(f"provider.mode mode={selected_mode} signal_source=fallback signal_count={len(signals)}")
        else:
            logger.info(f"provider.mode mode={selected_mode} signal_source=model signal_count={len(signals)}")
        return ResearchProviderResult(mode=selected_mode, signals=signals, source_pages=[], citations_count=0)

    if stage_callback:
        await stage_callback("planning_queries")
    tasks = await plan_search_tasks(brief, selected_mode, client=client)
    if stage_callback:
        await stage_callback("fetching_sources")
    pages = await gather_source_pages(tasks, mode=selected_mode)
    if stage_callback:
        await stage_callback("extracting_signals")
    model_signals = await extract_signals_with_model(brief, pages, client=client)
    signals = model_signals or heuristic_signals_from_pages(pages)
    signal_source = "model" if model_signals else "heuristic"
    source_pages = [
        {
            "title": page.title,
            "url": page.url,
            "source": page.source,
            "query": page.query,
        }
        for page in pages
    ]
    citations_count = len({page.url for page in pages if page.url})
    logger.info(
        f"provider.mode mode={selected_mode} signal_source={signal_source} "
        f"signal_count={len(signals)} citations_count={citations_count}"
    )
    return ResearchProviderResult(
        mode=selected_mode,
        signals=signals,
        source_pages=source_pages,
        citations_count=citations_count,
    )
