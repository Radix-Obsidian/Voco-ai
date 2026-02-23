# PowerShell build script for Windows
# Builds the synapse-mcp standalone executable and copies it to Tauri binaries

Write-Host "🚀 Building Voco Synapse MCP Server (Windows)" -ForegroundColor Cyan
Write-Host ""

# Ensure we're in the synapse-mcp directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Install dependencies if needed
Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
pip install -e ".[dev]"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Run the Python build script
Write-Host ""
Write-Host "🔨 Running PyInstaller build..." -ForegroundColor Yellow
python build.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Build complete!" -ForegroundColor Green
Write-Host "   Binary: services/mcp-gateway/src-tauri/binaries/synapse-mcp.exe" -ForegroundColor Gray
