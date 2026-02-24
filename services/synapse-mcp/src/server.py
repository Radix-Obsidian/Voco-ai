"""Voco Synapse MCP Server — YouTube video analysis via Gemini 1.5 Pro.

Exposes a single high-level tool that downloads a YouTube video, uploads it to
the Gemini File API, and extracts technical code/architecture using multimodal vision.

Critical: All logging goes to stderr to prevent stdout corruption of the JSON-RPC stream.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Configure logging to ONLY use stderr (never stdout, which would corrupt JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP("voco-synapse")


@mcp.tool()
async def analyze_video(url: str, extraction_goal: str) -> str:
    """Download a YouTube video and extract technical code/architecture using Gemini 1.5 Pro.
    
    This tool handles the complete pipeline:
    1. Download the video locally at max 720p resolution
    2. Upload to Google Gemini File API
    3. Process with gemini-1.5-pro multimodal vision
    4. Extract code, UI changes, and architectural diagrams
    5. Clean up all files (local + Gemini API)
    
    Args:
        url: YouTube video URL to analyze
        extraction_goal: What the user wants to extract (e.g., "Extract the exact React code shown on screen")
    
    Returns:
        Detailed markdown response with extracted code/architecture, or helpful error message
    """
    import google.generativeai as genai
    import yt_dlp
    
    temp_dir = None
    video_path = None
    uploaded_file = None
    
    try:
        # Validate API key is configured
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return (
                "Error: No Gemini API key configured. Please set GOOGLE_API_KEY or "
                "GEMINI_API_KEY environment variable in voco-mcp.json."
            )
        
        genai.configure(api_key=api_key)
        
        # Create cross-platform temp directory
        temp_dir = Path(tempfile.gettempdir()) / f"voco_synapse_{int(time.time())}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created temp directory: {temp_dir}")
        
        # Download video with yt-dlp (max 720p to balance quality vs file size)
        video_path = temp_dir / "video.mp4"
        ydl_opts = {
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
            "outtmpl": str(video_path),
            "quiet": True,
            "no_warnings": True,
            "logger": logger,
        }
        
        logger.info(f"Downloading video from: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if not video_path.exists():
            return f"Error: Failed to download video from {url}. Verify the URL is public and valid."
        
        logger.info(f"Video downloaded successfully ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")
        
        # Upload to Gemini File API
        logger.info("Uploading video to Gemini File API...")
        uploaded_file = genai.upload_file(str(video_path))
        
        # Poll until file is ACTIVE (required before generation)
        logger.info(f"Waiting for file processing (name: {uploaded_file.name})...")
        while uploaded_file.state.name == "PROCESSING":
            await asyncio.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)
        
        if uploaded_file.state.name != "ACTIVE":
            return f"Error: Gemini file upload failed with state: {uploaded_file.state.name}"
        
        logger.info("File is ACTIVE, generating analysis...")
        
        # Generate analysis with gemini-1.5-pro
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"""You are a senior engineer reverse-engineering this video.

The user's goal is: {extraction_goal}

Extract the exact code written on screen, UI state changes, and architectural diagrams. 
Output a highly detailed Markdown response with:
- **Code Blocks**: Wrap all code in proper markdown fenced blocks with language identifiers
- **Architecture**: Describe system architecture, component relationships, and data flow
- **UI Changes**: Document all visual state changes, transitions, and interactions shown
- **Annotations**: Add explanatory comments where the video shows important implementation details

Be extremely thorough and precise. This is for production implementation."""
        
        response = model.generate_content([uploaded_file, prompt])
        
        if not response or not response.text:
            return "Error: Gemini returned an empty response. The video may be too long or unsupported."
        
        logger.info("Analysis complete, cleaning up...")
        return response.text
        
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error: {e}")
        return f"Error: Failed to download video. {str(e)}. Verify the URL is a valid, public YouTube video."
    
    except Exception as e:
        logger.exception("Unexpected error in analyze_video")
        return f"Error: {type(e).__name__}: {str(e)}. Check server logs for details."
    
    finally:
        # Always clean up resources
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
                logger.info(f"Deleted Gemini file: {uploaded_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete Gemini file: {e}")
        
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Deleted temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to delete temp directory: {e}")


if __name__ == "__main__":
    # Run the MCP server over stdio
    mcp.run()
