# Voco V2 Dogfood Startup Script
# Launches cognitive-engine, LiteLLM, and Tauri desktop app in parallel

Write-Host "🚀 Starting Voco V2 Dogfood Environment..." -ForegroundColor Cyan

# Check if cognitive-engine is already running
$engineRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        $engineRunning = $true
        Write-Host "✅ Cognitive engine already running on :8001" -ForegroundColor Green
    }
} catch {
    Write-Host "⏳ Cognitive engine not detected, starting..." -ForegroundColor Yellow
}

# Start cognitive-engine if not running
if (-not $engineRunning) {
    Write-Host "Starting FastAPI engine..." -ForegroundColor Cyan
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k cd services\cognitive-engine && uv run uvicorn src.main:app --host 0.0.0.0 --port 8001" -WindowStyle Normal
    Start-Sleep -Seconds 3
}

# Start LiteLLM proxy
Write-Host "Starting LiteLLM proxy on :4000..." -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" -ArgumentList "/k cd services\cognitive-engine && uv run litellm --config litellm_config.yaml --port 4000" -WindowStyle Normal
Start-Sleep -Seconds 2

# Start Tauri desktop app
Write-Host "Starting Tauri desktop app..." -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" -ArgumentList "/k cd services\mcp-gateway && npm run dev:tauri" -WindowStyle Normal

Write-Host ""
Write-Host "✅ All services starting..." -ForegroundColor Green
Write-Host ""
Write-Host "📋 Services:" -ForegroundColor Cyan
Write-Host "  • Cognitive Engine: http://localhost:8001/health" -ForegroundColor Gray
Write-Host "  • LiteLLM Proxy: http://localhost:4000/health" -ForegroundColor Gray
Write-Host "  • Tauri App: Opening in new window" -ForegroundColor Gray
Write-Host ""
Write-Host "📖 Dogfood guide: DOGFOOD_SESSION.md" -ForegroundColor Cyan
Write-Host ""
