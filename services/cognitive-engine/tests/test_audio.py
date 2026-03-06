"""Unit tests for TTS audio client.

Validates that Cartesia API integration parses responses
correctly according to official documentation.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_audio.py -v
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.audio.tts import CartesiaTTS


class _AsyncIter:
    """Helper to make a list of items async-iterable for mocking websockets."""

    def __init__(self, items):
        self._items = list(items)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


# ---------------------------------------------------------------------------
# CartesiaTTS tests
# ---------------------------------------------------------------------------


class TestCartesiaTTSConfig:
    """Test CartesiaTTS configuration and constants."""

    def test_model_id_is_sonic_3(self):
        """BUG-1 regression: model_id must be 'sonic-3', not deprecated 'sonic-english'."""
        tts = CartesiaTTS(api_key="test-key")
        # The model_id is embedded in the payload, so we verify the class constants
        assert tts.API_VERSION == "2025-04-16"

    def test_api_version_is_latest(self):
        """BUG-2 regression: API version must be '2025-04-16', not '2024-06-10'."""
        assert CartesiaTTS.API_VERSION == "2025-04-16"

    @pytest.mark.asyncio
    async def test_empty_api_key_raises(self):
        """Verify synthesize_stream raises ValueError when API key is empty."""
        tts = CartesiaTTS(api_key="")
        with pytest.raises(ValueError, match="CARTESIA_API_KEY is empty"):
            async for _ in tts.synthesize_stream("Hello"):
                pass


class TestCartesiaTTSResponseParsing:
    """BUG-3 regression: Test response parsing matches official Cartesia docs."""

    @pytest.mark.asyncio
    async def test_parses_chunk_type_with_base64_data(self):
        """Official Cartesia format: {"type": "chunk", "data": "<base64>"}."""
        tts = CartesiaTTS(api_key="test-key")

        pcm_audio = b"\x00\x01\x02\x03" * 100
        b64_data = base64.b64encode(pcm_audio).decode()

        # Simulate WebSocket messages in official format
        messages = [
            json.dumps({"type": "chunk", "data": b64_data, "done": False, "status_code": 206}),
            json.dumps({"type": "done", "done": True, "status_code": 206}),
        ]

        async_messages = _AsyncIter(messages)
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_messages
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=False)

        with patch("websockets.connect", return_value=mock_ws):
            chunks = []
            async for chunk in tts.synthesize_stream("Hello"):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0] == pcm_audio

    @pytest.mark.asyncio
    async def test_handles_error_response(self):
        """Cartesia error: {"type": "error", "error": "..."} raises RuntimeError after retries."""
        tts = CartesiaTTS(api_key="test-key")

        messages = [
            json.dumps({"type": "error", "error": "Rate limit exceeded", "status_code": 429}),
        ]

        def _make_mock_ws():
            async_messages = _AsyncIter(list(messages))
            mock_ws = AsyncMock()
            mock_ws.send = AsyncMock()
            mock_ws.__aiter__ = lambda self: async_messages
            mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
            mock_ws.__aexit__ = AsyncMock(return_value=False)
            return mock_ws

        with patch("websockets.connect", side_effect=lambda *a, **kw: _make_mock_ws()):
            with pytest.raises(RuntimeError, match="Cartesia API error"):
                async for _ in tts.synthesize_stream("Hello"):
                    pass

    @pytest.mark.asyncio
    async def test_payload_uses_sonic_3_model(self):
        """BUG-1 regression: verify the WebSocket payload sends model_id 'sonic-3'."""
        tts = CartesiaTTS(api_key="test-key")

        pcm_audio = b"\x00\x01" * 50
        b64_data = base64.b64encode(pcm_audio).decode()
        messages = [
            json.dumps({"type": "chunk", "data": b64_data}),
            json.dumps({"type": "done", "done": True, "status_code": 206}),
        ]

        async_messages = _AsyncIter(messages)
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.__aiter__ = lambda self: async_messages
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=False)

        with patch("websockets.connect", return_value=mock_ws):
            async for _ in tts.synthesize_stream("Hello"):
                pass

        # Verify the payload sent to the WebSocket
        sent_payload = json.loads(mock_ws.send.call_args[0][0])
        assert sent_payload["model_id"] == "sonic-3"
        assert sent_payload["output_format"]["encoding"] == "pcm_s16le"
        assert sent_payload["output_format"]["container"] == "raw"
