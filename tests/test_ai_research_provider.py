from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from tools.ai_research_provider import (
    extract_city_hint,
    fallback_search_tasks,
    run_research_provider,
)
from tools.collectors.web_search_collector import SearchResult


class AIResearchProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.brief = {
            "product_name": "AI WhatsApp chatbot for shops",
            "product_description": (
                "Customers message a shop on WhatsApp and AI replies in Nepali and English "
                "with product info, price, and availability."
            ),
            "target_customer_guess": "Customer in morang for small shops",
            "pricing_model": "Monthly subscription",
            "competitor_examples": [],
            "research_goal": "Identify the best shops to go through and what should I charge them",
        }

    def test_extract_city_hint_preserves_custom_location(self) -> None:
        self.assertEqual(extract_city_hint("Customer in morang for small shops"), "Morang")

    def test_fallback_search_tasks_preserve_business_segment_and_location(self) -> None:
        tasks = fallback_search_tasks(self.brief, mode="free_first")
        self.assertEqual(tasks[0].city, "Morang")
        self.assertIn("small retail shops Morang", tasks[0].query)

    async def test_fast_draft_returns_uncited_ai_hypotheses(self) -> None:
        result = await run_research_provider(self.brief, mode="fast_draft")
        self.assertEqual(result.mode, "fast_draft")
        self.assertEqual(result.citations_count, 0)
        self.assertEqual(result.source_pages, [])
        self.assertGreaterEqual(len(result.signals), 3)

    async def test_fast_draft_prefers_model_output_when_available(self) -> None:
        model_signals = [
            {
                "source": "ai_draft",
                "subject": "Small Morang shops with WhatsApp demand",
                "signal_type": "icp",
                "segment": "ecommerce and retail",
                "city": "Morang",
                "channel": "WhatsApp",
                "confidence": 0.71,
                "notes": "Model-generated draft signal.",
                "url": "",
            }
        ]
        with patch(
            "tools.ai_research_provider.generate_draft_signals_with_model",
            new=AsyncMock(return_value=model_signals),
        ):
            result = await run_research_provider(self.brief, mode="fast_draft")
        self.assertEqual(result.mode, "fast_draft")
        self.assertEqual(len(result.signals), 1)
        self.assertEqual(result.signals[0]["subject"], "Small Morang shops with WhatsApp demand")

    async def test_free_first_falls_back_to_heuristic_signals_with_urls(self) -> None:
        from tools.ai_research_provider import SearchTask

        fake_tasks = [
            SearchTask(query="Morang retailers WhatsApp", signal_type="icp", city="Morang"),
            SearchTask(query="Facebook Morang sellers", signal_type="channel", city="Morang"),
            SearchTask(query="Morang business directory", signal_type="lead_source", city="Morang"),
            SearchTask(query="WhatsApp chatbot alternatives Nepal", signal_type="competitor", city="Morang"),
        ]
        fake_batches = [
            [SearchResult(title="Morang retailers use WhatsApp", body="Retail shops in Morang reply to WhatsApp buyers.", href="https://example.com/icp")],
            [SearchResult(title="Facebook sellers in Morang", body="Facebook and Instagram shops push buyers into WhatsApp.", href="https://example.com/channel")],
            [SearchResult(title="Morang business directory", body="Directory of local retail businesses and sellers.", href="https://example.com/leads")],
            [SearchResult(title="Chatbot software alternatives", body="Software alternatives for shop messaging and automation.", href="https://example.com/competitor")],
        ]
        with patch(
            "tools.ai_research_provider.plan_search_tasks",
            new=AsyncMock(return_value=fake_tasks),
        ), patch(
            "tools.ai_research_provider.search_text_results",
            new=AsyncMock(side_effect=fake_batches),
        ), patch(
            "tools.ai_research_provider.fetch_page_excerpt",
            new=AsyncMock(return_value="Fetched source excerpt."),
        ), patch(
            "tools.ai_research_provider.extract_signals_with_model",
            new=AsyncMock(return_value=[]),
        ), patch(
            "tools.ai_research_provider._tavily_active",
            return_value=False,
        ):
            result = await run_research_provider(self.brief, mode="free_first")
        self.assertEqual(result.mode, "free_first")
        self.assertEqual(result.citations_count, 4)
        self.assertEqual(len(result.source_pages), 4)
        self.assertTrue(all(signal["url"] for signal in result.signals))
        self.assertEqual({signal["signal_type"] for signal in result.signals}, {"icp", "channel", "lead_source", "competitor"})

    async def test_free_first_with_tavily_skips_fetch_page_excerpt(self) -> None:
        fake_batches = [
            [SearchResult(title="Morang shops WhatsApp", body="WhatsApp usage among Morang retailers.", href="https://example.com/icp", score=0.88, raw_content="Full page content about Morang retailers.")],
            [SearchResult(title="Facebook Morang sellers", body="Facebook group for Morang shop owners.", href="https://example.com/channel", score=0.75, raw_content="Full page content about Facebook channels.")],
            [SearchResult(title="Business directory Morang", body="Nepal business directory listing.", href="https://example.com/leads", score=0.70, raw_content="")],
            [SearchResult(title="WhatsApp bot alternatives", body="Chatbot software for small shops.", href="https://example.com/competitor", score=0.65, raw_content="")],
        ]
        with patch(
            "tools.ai_research_provider.search_text_results",
            new=AsyncMock(side_effect=fake_batches),
        ), patch(
            "tools.ai_research_provider.fetch_page_excerpt",
            new=AsyncMock(return_value="should not be called"),
        ) as mock_fetch, patch(
            "tools.ai_research_provider.extract_signals_with_model",
            new=AsyncMock(return_value=[]),
        ), patch(
            "tools.ai_research_provider._tavily_active",
            return_value=True,
        ):
            result = await run_research_provider(self.brief, mode="free_first")
        mock_fetch.assert_not_called()
        self.assertEqual(result.mode, "free_first")
        self.assertEqual(result.citations_count, 4)
        self.assertTrue(all(signal["url"] for signal in result.signals))

    async def test_grounded_paid_uses_advanced_depth(self) -> None:
        from tools.ai_research_provider import _search_depth_for_mode
        self.assertEqual(_search_depth_for_mode("grounded_paid"), "advanced")
        self.assertEqual(_search_depth_for_mode("free_first"), "basic")
        self.assertEqual(_search_depth_for_mode("fast_draft"), "basic")

    async def test_grounded_paid_passes_include_raw_content(self) -> None:
        fake_batches = [
            [SearchResult(title="Nepal CRM market", body="CRM demand in Nepal.", href="https://example.com/icp", score=0.91, raw_content="Detailed CRM market analysis for Nepal.")],
            [SearchResult(title="Nepal channels", body="Facebook groups.", href="https://example.com/channel", score=0.80, raw_content="")],
        ]
        captured_kwargs: list[dict] = []

        async def capturing_search(query, max_results, **kwargs):
            captured_kwargs.append(kwargs)
            return fake_batches.pop(0) if fake_batches else []

        with patch(
            "tools.ai_research_provider.search_text_results",
            new=capturing_search,
        ), patch(
            "tools.ai_research_provider.extract_signals_with_model",
            new=AsyncMock(return_value=[]),
        ), patch(
            "tools.ai_research_provider._tavily_active",
            return_value=True,
        ), patch(
            "tools.ai_research_provider.plan_search_tasks",
            new=AsyncMock(return_value=[
                __import__("tools.ai_research_provider", fromlist=["SearchTask"]).SearchTask(
                    query="Nepal CRM market", signal_type="icp", city="Kathmandu"
                ),
                __import__("tools.ai_research_provider", fromlist=["SearchTask"]).SearchTask(
                    query="Nepal channels", signal_type="channel", city="Kathmandu"
                ),
            ]),
        ):
            await run_research_provider(self.brief, mode="grounded_paid")

        self.assertTrue(
            any(kwargs.get("search_depth") == "advanced" for kwargs in captured_kwargs),
            "Expected at least one call with search_depth='advanced'"
        )
        self.assertTrue(
            any(kwargs.get("include_raw_content") is True for kwargs in captured_kwargs),
            "Expected include_raw_content=True for grounded_paid mode"
        )


if __name__ == "__main__":
    unittest.main()
