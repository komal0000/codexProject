from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tools.tavily_client import TavilySearchClient, TavilySearchResult


def _fake_tavily_response(results: list[dict]) -> dict:
    return {"results": results}


class TavilySearchClientTests(unittest.IsolatedAsyncioTestCase):
    def test_enabled_false_when_no_api_key(self) -> None:
        client = TavilySearchClient(api_key="")
        self.assertFalse(client.enabled)

    def test_enabled_true_when_api_key_provided(self) -> None:
        client = TavilySearchClient(api_key="tvly-test-key")
        self.assertTrue(client.enabled)

    async def test_search_returns_empty_when_disabled(self) -> None:
        client = TavilySearchClient(api_key="")
        results = await client.search("Nepal CRM market")
        self.assertEqual(results, [])

    async def test_search_maps_response_to_results(self) -> None:
        fake_response = _fake_tavily_response(
            [
                {
                    "title": "CRM tools Nepal",
                    "url": "https://example.com/crm-nepal",
                    "content": "Snippet about CRM tools in Kathmandu.",
                    "raw_content": "Full page text about CRM.",
                    "score": 0.87,
                },
                {
                    "title": "Lead management in Nepal",
                    "url": "https://example.com/leads",
                    "content": "Lead management for small Kathmandu startups.",
                    "raw_content": "",
                    "score": 0.72,
                },
            ]
        )

        mock_sdk_client = MagicMock()
        mock_sdk_client.search.return_value = fake_response

        client = TavilySearchClient(api_key="tvly-test-key")
        with patch.object(client, "_client", return_value=mock_sdk_client):
            results = await client.search(
                "CRM Nepal",
                max_results=5,
                search_depth="basic",
                country="nepal",
            )

        self.assertEqual(len(results), 2)
        first = results[0]
        self.assertIsInstance(first, TavilySearchResult)
        self.assertEqual(first.title, "CRM tools Nepal")
        self.assertEqual(first.url, "https://example.com/crm-nepal")
        self.assertEqual(first.score, 0.87)
        self.assertEqual(first.raw_content, "Full page text about CRM.")

    async def test_search_returns_empty_on_exception(self) -> None:
        client = TavilySearchClient(api_key="tvly-test-key")

        def raise_error(*args, **kwargs):
            raise RuntimeError("API error")

        with patch.object(client, "_search_sync", side_effect=raise_error):
            results = await client.search("Nepal market", timeout_seconds=0.05)
        self.assertEqual(results, [])

    async def test_search_passes_exclude_domains(self) -> None:
        fake_response = _fake_tavily_response([])
        mock_sdk_client = MagicMock()
        mock_sdk_client.search.return_value = fake_response

        client = TavilySearchClient(api_key="tvly-test-key")
        with patch.object(client, "_client", return_value=mock_sdk_client):
            await client.search(
                "HubSpot Nepal pricing",
                exclude_domains=["reddit.com", "alternativeto.net"],
            )

        call_kwargs = mock_sdk_client.search.call_args.kwargs
        self.assertIn("exclude_domains", call_kwargs)
        self.assertIn("reddit.com", call_kwargs["exclude_domains"])


if __name__ == "__main__":
    unittest.main()
