from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.openrouter_client import OpenRouterClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url, headers=None, json=None):
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "{\"ok\": true}"
                        }
                    }
                ]
            }
        )


class OpenRouterClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_json_logs_success_when_response_is_valid(self) -> None:
        client = OpenRouterClient(api_key="test-key", model="openrouter/free")
        with patch("tools.openrouter_client.httpx.AsyncClient", FakeAsyncClient), patch(
            "tools.openrouter_client.logger"
        ) as mock_logger:
            payload = await client.complete_json(
                system_prompt="Return JSON only.",
                user_prompt="Return {'ok': true}.",
            )
        self.assertEqual(payload, {"ok": True})
        info_messages = [call.args[0] for call in mock_logger.info.call_args_list]
        self.assertTrue(any("openrouter.request_started" in message for message in info_messages))
        self.assertTrue(any("openrouter.request_succeeded" in message for message in info_messages))


if __name__ == "__main__":
    unittest.main()
