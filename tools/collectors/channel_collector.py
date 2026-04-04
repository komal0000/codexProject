from __future__ import annotations

import asyncio

from .web_search_collector import collect_from_web_search


async def collect_channels(
    segment: str,
    city: str = "Kathmandu",
) -> list[dict[str, object]]:
    queries = [
        f"{segment} Nepal Facebook marketing",
        f"{segment} Nepal LinkedIn",
        f"{segment} Nepal Instagram shop",
        f"{segment} Nepal TikTok business",
    ]
    tasks = [collect_from_web_search(query, signal_type="channel", city=city, max_results=5) for query in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for batch in results:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            key = (str(item["signal_type"]), str(item["subject"]).lower(), str(item["url"]).lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged
