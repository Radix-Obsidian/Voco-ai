"""Tests for the Voco Synapse MCP Server — analyze_video tool.

Run:
    cd services/synapse-mcp
    uv run pytest tests/test_synapse_server.py -v
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. MCP server starts without crash
# ---------------------------------------------------------------------------


class TestSynapseServerInit:
    def test_fastmcp_initialises_with_analyze_video(self):
        from src.server import mcp

        assert mcp.name == "voco-synapse"
        # The tool should be registered via @mcp.tool()
        tools = mcp._tool_manager._tools
        assert "analyze_video" in tools


# ---------------------------------------------------------------------------
# 2. analyze_video rejects missing API key
# ---------------------------------------------------------------------------


class TestAnalyzeVideoMissingKey:
    @pytest.mark.asyncio
    async def test_rejects_missing_api_key(self):
        from src.server import analyze_video

        # Ensure no API key is set
        env_patch = {"GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""}
        with patch.dict(os.environ, env_patch, clear=False):
            # Temporarily remove keys if they exist
            for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
                os.environ.pop(k, None)

            result = await analyze_video(
                url="https://www.youtube.com/watch?v=test123",
                extraction_goal="Extract code",
            )
            assert "Error" in result
            assert "Gemini API key" in result


# ---------------------------------------------------------------------------
# 3. analyze_video rejects invalid URL
# ---------------------------------------------------------------------------


class TestAnalyzeVideoInvalidURL:
    @pytest.mark.asyncio
    async def test_rejects_invalid_url(self):
        from src.server import analyze_video

        mock_genai = MagicMock()
        mock_genai.configure = MagicMock()

        # Simulate yt-dlp DownloadError
        import yt_dlp.utils

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}), \
             patch("src.server.genai", mock_genai):
            # Mock yt_dlp to raise DownloadError
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
            mock_ydl_instance.__exit__ = MagicMock(return_value=False)
            mock_ydl_instance.download.side_effect = yt_dlp.utils.DownloadError("Video unavailable")

            with patch("src.server.yt_dlp.YoutubeDL", return_value=mock_ydl_instance):
                result = await analyze_video(
                    url="https://youtube.com/watch?v=INVALID",
                    extraction_goal="Extract code",
                )
                assert "Error" in result
                assert "download" in result.lower() or "Download" in result


# ---------------------------------------------------------------------------
# 4. analyze_video cleanup on success
# ---------------------------------------------------------------------------


class TestAnalyzeVideoCleanupSuccess:
    @pytest.mark.asyncio
    async def test_cleanup_on_success(self):
        from src.server import analyze_video

        mock_genai = MagicMock()
        mock_genai.configure = MagicMock()

        # Mock uploaded file
        mock_file = MagicMock()
        mock_file.name = "files/test-file-123"
        mock_file.state = MagicMock()
        mock_file.state.name = "ACTIVE"
        mock_genai.upload_file = MagicMock(return_value=mock_file)
        mock_genai.get_file = MagicMock(return_value=mock_file)
        mock_genai.delete_file = MagicMock()

        # Mock generation
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "# Analysis\n```python\nprint('hello')\n```"
        mock_model.generate_content = MagicMock(return_value=mock_response)
        mock_genai.GenerativeModel = MagicMock(return_value=mock_model)

        # Track temp directories created
        created_dirs: list[Path] = []

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}), \
             patch("src.server.genai", mock_genai):

            # Mock yt-dlp to create a fake video file
            def mock_download(urls):
                # Find the temp dir and create a fake video
                import glob
                tmp = Path(tempfile.gettempdir())
                synapse_dirs = list(tmp.glob("voco_synapse_*"))
                if synapse_dirs:
                    created_dirs.extend(synapse_dirs)
                    video = synapse_dirs[-1] / "video.mp4"
                    video.write_bytes(b"fake video content")

            mock_ydl_instance = MagicMock()
            mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
            mock_ydl_instance.__exit__ = MagicMock(return_value=False)
            mock_ydl_instance.download = mock_download

            with patch("src.server.yt_dlp.YoutubeDL", return_value=mock_ydl_instance):
                result = await analyze_video(
                    url="https://youtube.com/watch?v=demo123",
                    extraction_goal="Extract code",
                )

        # Verify cleanup was called
        mock_genai.delete_file.assert_called_once_with("files/test-file-123")
        # Verify result contains the analysis
        assert "Analysis" in result or "hello" in result


# ---------------------------------------------------------------------------
# 5. analyze_video cleanup on failure
# ---------------------------------------------------------------------------


class TestAnalyzeVideoCleanupFailure:
    @pytest.mark.asyncio
    async def test_cleanup_on_failure(self):
        from src.server import analyze_video

        mock_genai = MagicMock()
        mock_genai.configure = MagicMock()

        # Mock uploaded file
        mock_file = MagicMock()
        mock_file.name = "files/test-file-456"
        mock_file.state = MagicMock()
        mock_file.state.name = "ACTIVE"
        mock_genai.upload_file = MagicMock(return_value=mock_file)
        mock_genai.get_file = MagicMock(return_value=mock_file)
        mock_genai.delete_file = MagicMock()

        # Mock generation to FAIL
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = RuntimeError("Gemini API error")
        mock_genai.GenerativeModel = MagicMock(return_value=mock_model)

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}), \
             patch("src.server.genai", mock_genai):

            def mock_download(urls):
                tmp = Path(tempfile.gettempdir())
                synapse_dirs = list(tmp.glob("voco_synapse_*"))
                if synapse_dirs:
                    video = synapse_dirs[-1] / "video.mp4"
                    video.write_bytes(b"fake video")

            mock_ydl_instance = MagicMock()
            mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
            mock_ydl_instance.__exit__ = MagicMock(return_value=False)
            mock_ydl_instance.download = mock_download

            with patch("src.server.yt_dlp.YoutubeDL", return_value=mock_ydl_instance):
                result = await analyze_video(
                    url="https://youtube.com/watch?v=demo456",
                    extraction_goal="Extract code",
                )

        # Verify cleanup was still called despite the error
        mock_genai.delete_file.assert_called_once_with("files/test-file-456")
        # Verify error message returned
        assert "Error" in result
        assert "RuntimeError" in result or "Gemini API error" in result
