from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from tools.collectors import collect_all_live_signals
from tools.collectors.competitor_collector_refined import collect_competitors
from tools.collectors.web_search_collector import SearchResult, collect_from_web_search


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_from_web_search_maps_results(self) -> None:
        fake_results = [
            SearchResult(
                title="CRM software Nepal pricing",
                body="Kathmandu startups compare CRM pricing and lightweight tools.",
                href="https://example.com/crm-nepal",
            ),
            SearchResult(
                title="Lead management tools for agencies",
                body="Agencies in Nepal use LinkedIn and search to evaluate tools.",
                href="https://example.com/agencies",
            ),
        ]
        with patch(
            "tools.collectors.web_search_collector.search_text_results",
            new=AsyncMock(return_value=fake_results),
        ):
            signals = await collect_from_web_search(
                query="CRM software Nepal Kathmandu",
                signal_type="icp",
                city="Kathmandu",
                max_results=2,
            )
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0]["source"], "example.com")
        self.assertEqual(signals[0]["confidence"], 0.8)
        self.assertEqual(signals[0]["city"], "Kathmandu")

    async def test_collect_all_live_signals_continues_when_one_collector_fails(self) -> None:
        brief = {
            "product_name": "PipelinePilot",
            "product_description": "Lead capture and follow-up for small teams.",
            "target_customer_guess": "Urban Nepal service businesses",
            "pricing_model": "subscription",
            "competitor_examples": ["Zoho CRM"],
            "research_goal": "Find channels",
        }
        with patch(
            "tools.collectors.collect_from_web_search",
            new=AsyncMock(
                return_value=[
                    {
                        "signal_type": "icp",
                        "subject": "ICP",
                        "url": "https://a",
                        "source": "a",
                        "segment": "smes",
                        "city": "Kathmandu",
                        "channel": "Google Search",
                        "confidence": 0.8,
                        "notes": "note",
                    }
                ]
            ),
        ), patch(
            "tools.collectors.collect_competitors",
            new=AsyncMock(side_effect=RuntimeError("search unavailable")),
        ), patch(
            "tools.collectors.collect_channels",
            new=AsyncMock(
                return_value=[
                    {
                        "signal_type": "channel",
                        "subject": "Facebook use",
                        "url": "https://b",
                        "source": "b",
                        "segment": "smes",
                        "city": "Kathmandu",
                        "channel": "Facebook",
                        "confidence": 0.65,
                        "notes": "note",
                    }
                ]
            ),
        ):
            signals = await collect_all_live_signals(brief, max_per_collector=3)
        self.assertEqual({item["signal_type"] for item in signals}, {"icp", "channel"})

    async def test_collect_all_live_signals_times_out_hung_collector(self) -> None:
        brief = {
            "product_name": "PipelinePilot",
            "product_description": "Lead capture and follow-up for small teams.",
            "target_customer_guess": "Urban Nepal service businesses",
            "pricing_model": "subscription",
            "competitor_examples": ["Zoho CRM"],
            "research_goal": "Find channels",
        }

        async def slow_competitor_collector(*args, **kwargs):
            await asyncio.sleep(60)
            return []

        with patch(
            "tools.collectors.collect_from_web_search",
            new=AsyncMock(
                return_value=[
                    {
                        "signal_type": "icp",
                        "subject": "ICP",
                        "url": "https://a",
                        "source": "a",
                        "segment": "smes",
                        "city": "Kathmandu",
                        "channel": "Google Search",
                        "confidence": 0.8,
                        "notes": "note",
                    }
                ]
            ),
        ), patch(
            "tools.collectors.collect_competitors",
            new=slow_competitor_collector,
        ), patch(
            "tools.collectors.collect_channels",
            new=AsyncMock(return_value=[]),
        ):
            signals = await collect_all_live_signals(
                brief,
                max_per_collector=3,
                collector_timeout_seconds=0.01,
            )
        self.assertEqual({item["signal_type"] for item in signals}, {"icp"})

    async def test_collect_competitors_prefers_official_brand_result(self) -> None:
        fake_results = [
            [
                SearchResult(
                    title="HubSpot Pricing 2026 Guide",
                    body="Independent pricing guide for HubSpot.",
                    href="https://emailvendorselection.com/hubspot-pricing",
                ),
                SearchResult(
                    title="What is HubSpot?",
                    body="Forum-style discussion about HubSpot.",
                    href="https://www.zhihu.com/question/500051166",
                ),
            ],
            [
                SearchResult(
                    title="HubSpot Starter Customer Platform for Startups",
                    body="Official HubSpot starter CRM pricing page.",
                    href="https://www.hubspot.com/products/crm/starter",
                ),
            ]
        ]
        with patch(
            "tools.collectors.competitor_collector_refined.search_text_results",
            new=AsyncMock(side_effect=fake_results),
        ):
            signals = await collect_competitors(
                product_description="Lead capture and follow-up for small teams.",
                competitor_examples=["HubSpot Starter"],
                city="Nepal",
                max_results=5,
            )
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["subject"], "HubSpot Starter")
        self.assertEqual(signals[0]["source"], "hubspot.com")

    async def test_collect_competitors_uses_trusted_review_when_official_missing(self) -> None:
        fake_results = [
            [
                SearchResult(
                    title="Zoho CRM Pricing",
                    body="Compare Zoho CRM plans and pricing.",
                    href="https://www.g2.com/products/zoho-crm/pricing",
                ),
                SearchResult(
                    title="Zoho CRM discussion thread",
                    body="Forum conversation about Zoho CRM.",
                    href="https://www.zhihu.com/question/482475952",
                ),
            ],
            [],
        ]
        with patch(
            "tools.collectors.competitor_collector_refined.search_text_results",
            new=AsyncMock(side_effect=fake_results),
        ):
            signals = await collect_competitors(
                product_description="Lead capture and follow-up for small teams.",
                competitor_examples=["Zoho CRM"],
                city="Nepal",
                max_results=5,
            )
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["subject"], "Zoho CRM")
        self.assertEqual(signals[0]["source"], "g2.com")


if __name__ == "__main__":
    unittest.main()
