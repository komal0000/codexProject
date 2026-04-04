from __future__ import annotations

import asyncio
from importlib.util import find_spec
from typing import Any

try:
    from nepal_market_lib import infer_city, normalize_whitespace
except ModuleNotFoundError:  # pragma: no cover
    from tools.nepal_market_lib import infer_city, normalize_whitespace

from .channel_collector import collect_channels
from .competitor_collector_refined import collect_competitors
from .web_search_collector import collect_from_web_search

if find_spec("loguru"):
    from loguru import logger
else:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)


def dedupe_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for signal in signals:
        key = (
            normalize_whitespace(signal.get("signal_type")),
            normalize_whitespace(signal.get("subject")).lower(),
            normalize_whitespace(signal.get("url")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped


async def collect_all_live_signals(
    brief: dict[str, Any],
    max_per_collector: int = 10,
) -> list[dict[str, Any]]:
    """
    Runs all collectors in parallel using asyncio.gather().
    Returns merged list of raw signal dicts.
    Each collector failure is caught and logged — never raises.
    """

    target_customer = normalize_whitespace(brief.get("target_customer_guess"))
    product_name = normalize_whitespace(brief.get("product_name"))
    product_description = normalize_whitespace(brief.get("product_description"))
    city_hint = infer_city(" ".join((target_customer, product_description)))
    tasks = [
        collect_from_web_search(
            query=f"{target_customer} Nepal market",
            signal_type="icp",
            city=city_hint,
            max_results=max_per_collector,
        ),
        collect_from_web_search(
            query=f"{product_name} Nepal lead sources",
            signal_type="lead_source",
            city=city_hint,
            max_results=max_per_collector,
        ),
        collect_competitors(
            product_description=product_description,
            competitor_examples=list(brief.get("competitor_examples", [])),
            city="Nepal",
            max_results=max_per_collector,
        ),
        collect_channels(segment=target_customer or product_name or "businesses", city=city_hint),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"live_collectors.failed error={result!s}")
            continue
        merged.extend(result)
    deduped = dedupe_signals(merged)
    logger.info(f"live_collectors.completed signals={len(deduped)}")
    return deduped


__all__ = [
    "collect_all_live_signals",
    "collect_channels",
    "collect_competitors",
    "collect_from_web_search",
]
