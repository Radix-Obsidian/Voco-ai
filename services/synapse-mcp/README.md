# Voco Synapse MCP Server

Production-grade Model Context Protocol (MCP) server that enables AI agents to analyze YouTube videos using Google Gemini 1.5 Pro's multimodal vision capabilities.

## Features

- **Single High-Level Tool**: Exposes one outcome-driven `analyze_video` tool instead of fragmented operations
- **Multimodal Video Analysis**: Leverages Gemini 1.5 Pro to extract code, UI changes, and architecture from screen recordings
- **Zero stdout Pollution**: All logging routes to `stderr` to prevent JSON-RPC stream corruption
- **Automatic Cleanup**: Deletes both local temp files and Gemini API uploads after processing
- **Cross-Platform**: Uses `tempfile.gettempdir()` for Windows/macOS/Linux compatibility
- **Bundled with Tauri**: Ships as a standalone executable with Voco desktop app — no Python installation required

## Production Deployment

This MCP server is **automatically bundled** with the Voco desktop application as a Tauri sidecar binary. End users do not need to install Python or any dependencies.

### Build Process (Developer Only)

To build the standalone executable for bundling:

**Windows:**
```powershell
cd services/synapse-mcp
.\build.ps1
```

**macOS/Linux:**
```bash
cd services/synapse-mcp
chmod +x build.sh
./build.sh
```

This creates a platform-specific binary in `services/mcp-gateway/src-tauri/binaries/`:
- Windows: `synapse-mcp.exe`
- macOS: `synapse-mcp-macos`
- Linux: `synapse-mcp-linux`

The binary is automatically included in the Tauri bundle via `tauri.conf.json` → `bundle.externalBin`.

## Configuration (End Users)

Users configure their Gemini API key through the Voco desktop app settings UI. The key is securely stored and passed to the MCP server via environment variables.

API key can be obtained from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Usage

The MCP server runs over `stdio` and is automatically discovered by Voco's `UniversalMCPRegistry`.

### Tool: `analyze_video`

**Description**: Downloads a YouTube video, uploads it to Gemini File API, extracts technical code/architecture, and returns detailed Markdown.

**Parameters**:
- `url` (string): YouTube video URL
- `extraction_goal` (string): What to extract (e.g., "Extract the React components and state management code shown on screen")

**Returns**: Detailed Markdown with code blocks, architecture descriptions, and UI change documentation.

**Example** (when called by an LLM through MCP):
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "extraction_goal": "Extract the exact TypeScript code and component hierarchy shown in the demo"
}
```

## Architecture

This server follows Anthropic's MCP best practices:

1. **Transport**: stdio (never use `print()` - only `logging` to stderr)
2. **Outcomes Over Operations**: Single tool handles the complete pipeline
3. **Contextual Errors**: Returns natural language error messages instead of stack traces

### Pipeline Flow

```
YouTube URL → yt-dlp (720p max) → Local Temp File → Gemini File API Upload
→ Poll for ACTIVE → Generate with gemini-1.5-pro → Return Markdown
→ Cleanup (delete Gemini file + local temp directory)
```

## Troubleshooting

**Error: No Gemini API key configured**
- Set `GOOGLE_API_KEY` or `GEMINI_API_KEY` environment variable

**Error: Failed to download video**
- Verify the YouTube URL is public and valid
- Check internet connection
- Some videos may be region-restricted or require authentication

**Error: Gemini file upload failed**
- Large videos (>2GB) may fail - yt-dlp is configured for max 720p to prevent this
- Check your Gemini API quota limits

## Development

Run tests:
```bash
pytest
```

Run the server standalone (for debugging):
```bash
python -m src.server
```

## Security

- API keys should never be hardcoded in the `voco-mcp.json` file
- Use environment variables or Voco's secure key storage
- The server automatically cleans up temporary files to prevent disk space leaks
- Downloaded videos are stored in system temp directory with restrictive permissions
