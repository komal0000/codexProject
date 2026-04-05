from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from nepal_market_lib import normalize_whitespace, source_from_url
except ModuleNotFoundError:  # pragma: no cover
    from tools.nepal_market_lib import normalize_whitespace, source_from_url

from .web_search_collector import SearchResult, build_signal, dedupe_raw_signals, search_text_results

IGNORED_COMPETITOR_DOMAINS = {
    "alternative.me",
    "alternativeto.net",
    "alternatives.co",
    "dictionary.cambridge.org",
    "emailvendorselection.com",
    "opensourcealternatives.to",
    "oxfordlearnersdictionaries.com",
    "reddit.com",
    "vtudien.com",
    "zhihu.com",
}
TRUSTED_REVIEW_DOMAINS = {
    "capterra.com",
    "g2.com",
    "getapp.com",
    "softwareadvice.com",
    "trustradius.com",
}
IGNORED_COMPETITOR_TERMS = (
    "alternative to",
    "alternatives to",
    "best alternatives",
    "compare",
    "dictionary",
    "definition",
    "directory",
    "forum",
    "meaning",
    "review site",
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


def competitor_keywords(label: str) -> list[str]:
    words = [token for token in re.findall(r"[a-zA-Z0-9]+", label.lower()) if len(token) > 2]
    return list(dict.fromkeys(words))


def competitor_subject(result: SearchResult, fallback: str) -> str:
    title = normalize_whitespace(result.title)
    if title:
        return title.split("-")[0].split("|")[0].strip() or fallback
    return fallback


def is_brand_match(result: SearchResult, keywords: list[str]) -> bool:
    haystack = normalize_whitespace(f"{result.title} {result.body} {result.href}").lower()
    return any(keyword in haystack for keyword in keywords)


def should_keep_result(result: SearchResult, expected_label: str | None = None) -> bool:
    source = source_from_url(result.href)
    if source in IGNORED_COMPETITOR_DOMAINS:
        return False
    haystack = normalize_whitespace(f"{result.title} {result.body}").lower()
    if source not in TRUSTED_REVIEW_DOMAINS and any(term in haystack for term in IGNORED_COMPETITOR_TERMS):
        return False
    if expected_label:
        keywords = competitor_keywords(expected_label)
        if not keywords or not is_brand_match(result, keywords):
            return False
    return True


def result_quality(result: SearchResult, expected_label: str) -> tuple[int, int, int]:
    keywords = competitor_keywords(expected_label)
    source = source_from_url(result.href)
    haystack = normalize_whitespace(f"{result.title} {result.body}").lower()
    official_domain = 3 if any(keyword in source for keyword in keywords) else 0
    trusted_review = 2 if source in TRUSTED_REVIEW_DOMAINS else 0
    title_match = 2 if any(keyword in normalize_whitespace(result.title).lower() for keyword in keywords) else 0
    commercial_page = 1 if any(token in haystack for token in ("pricing", "plans", "crm", "software", "platform")) else 0
    shorter_domain = -len(source)
    return (official_domain + trusted_review, title_match + commercial_page, shorter_domain)


async def collect_competitors(
    product_description: str,
    competitor_examples: list[str],
    city: str = "Nepal",
    max_results: int = 8,
) -> list[dict[str, Any]]:
    examples = [normalize_whitespace(example) for example in competitor_examples if normalize_whitespace(example)]
    queries: list[tuple[str, str | None]] = []
    for example in examples:
        queries.append((f"{example} Nepal pricing", example))
        queries.append((f"{example} pricing", example))
    queries = list(dict.fromkeys(queries))

    if not queries:
        product_hint = product_search_phrase(product_description)
        if product_hint:
            queries.append((f"{product_hint} software alternatives Nepal", None))

    exclude = list(IGNORED_COMPETITOR_DOMAINS)
    tasks = [
        search_text_results(query, max_results=max_results, exclude_domains=exclude)
        for query, _ in queries
    ]
    batches = await asyncio.gather(*tasks, return_exceptions=True)
    signals = []

    for (query, expected_label), batch in zip(queries, batches):
        if isinstance(batch, Exception):
            continue

        filtered_results = [
            result
            for result in batch
            if should_keep_result(result, expected_label=expected_label)
        ]

        if expected_label:
            filtered_results.sort(key=lambda item: result_quality(item, expected_label), reverse=True)
            filtered_results = filtered_results[:1]

        fallback_subject = (
            query.replace(" Nepal pricing", "")
            .replace(" software alternatives Nepal", "")
            .replace(" Nepal", "")
        )

        for position, result in enumerate(filtered_results, start=1):
            subject = expected_label or competitor_subject(result, fallback_subject)
            if not subject:
                continue
            signals.append(
                build_signal(
                    result,
                    signal_type="competitor",
                    city=city,
                    position=position,
                    subject_override=subject,
                )
            )

    return dedupe_raw_signals(signals)
