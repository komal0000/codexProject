from __future__ import annotations

import asyncio
import re

try:
    from nepal_market_lib import normalize_whitespace, source_from_url
except ModuleNotFoundError:  # pragma: no cover
    from tools.nepal_market_lib import normalize_whitespace, source_from_url

from .web_search_collector import SearchResult, build_signal, dedupe_raw_signals, search_text_results

IGNORED_COMPETITOR_DOMAINS = {
    "dictionary.cambridge.org",
    "oxfordlearnersdictionaries.com",
    "vtudien.com",
}
IGNORED_COMPETITOR_TERMS = (
    "dictionary",
    "definition",
    "meaning",
    "nghia",
    "từ điển",
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "helps",
    "into",
    "lightweight",
    "platform",
    "rollout",
    "small",
    "teams",
    "that",
    "the",
    "with",
    "without",
}


def product_search_phrase(product_description: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-zA-Z]+", product_description.lower())
        if len(token) > 3 and token not in STOPWORDS
    ]
    unique_tokens = list(dict.fromkeys(tokens))
    if not unique_tokens:
        return normalize_whitespace(product_description).split(".")[0]
    return " ".join(unique_tokens[:5])


def should_keep_result(result: SearchResult) -> bool:
    source = source_from_url(result.href)
    if source in IGNORED_COMPETITOR_DOMAINS:
        return False
    haystack = normalize_whitespace(f"{result.title} {result.body}").lower()
    return not any(term in haystack for term in IGNORED_COMPETITOR_TERMS)


def competitor_subject(result: SearchResult, fallback: str) -> str:
    title = normalize_whitespace(result.title)
    if title:
        return title.split("-")[0].split("|")[0].strip() or fallback
    return fallback


async def collect_competitors(
    product_description: str,
    competitor_examples: list[str],
    city: str = "Nepal",
    max_results: int = 8,
) -> list[dict[str, object]]:
    product_hint = product_search_phrase(product_description)
    queries = [f"{example} Nepal pricing" for example in competitor_examples if normalize_whitespace(example)]
    if product_hint:
        queries.append(f"{product_hint} software alternatives Nepal")
    queries = list(dict.fromkeys(queries))
    tasks = [search_text_results(query, max_results=max_results) for query in queries]
    batches = await asyncio.gather(*tasks, return_exceptions=True)
    signals = []
    for query, batch in zip(queries, batches):
        if isinstance(batch, Exception):
            continue
        fallback_subject = (
            query.replace(" Nepal pricing", "")
            .replace(" software alternatives Nepal", "")
            .replace(" Nepal", "")
        )
        for position, result in enumerate(batch, start=1):
            if not should_keep_result(result):
                continue
            signals.append(
                build_signal(
                    result,
                    signal_type="competitor",
                    city=city,
                    position=position,
                    subject_override=competitor_subject(result, fallback_subject),
                )
            )
    return dedupe_raw_signals(signals)
