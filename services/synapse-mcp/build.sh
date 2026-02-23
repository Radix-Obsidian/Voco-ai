#!/bin/bash
# Build script for macOS/Linux
# Builds the synapse-mcp standalone executable and copies it to Tauri binaries

set -e

echo "🚀 Building Voco Synapse MCP Server ($(uname -s))"
echo ""

# Ensure we're in the synapse-mcp directory
cd "$(dirname "$0")"

# Install dependencies if needed
echo "📦 Installing dependencies..."
pip install -e ".[dev]"

# Run the Python build script
echo ""
echo "🔨 Running PyInstaller build..."
python build.py

echo ""
echo "✅ Build complete!"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "   Binary: services/mcp-gateway/src-tauri/binaries/synapse-mcp-macos"
else
    echo "   Binary: services/mcp-gateway/src-tauri/binaries/synapse-mcp-linux"
fi
