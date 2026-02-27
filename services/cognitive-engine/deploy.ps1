# Voco Cognitive Engine - Quick Deploy Script for Windows
# Run this from: C:\Users\autre\Downloads\Voco V2\services\cognitive-engine

param(
    [string]$DropletIP = "146.190.121.108"
)

Write-Host "=== Voco Cognitive Engine Deployment ===" -ForegroundColor Green
Write-Host "Droplet IP: $DropletIP" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please copy .env.production to .env and add your API keys first:" -ForegroundColor Yellow
    Write-Host "  copy .env.production .env" -ForegroundColor Yellow
    Write-Host "  notepad .env" -ForegroundColor Yellow
    exit 1
}

# --- Step 1: Upload only the files Docker needs ---
Write-Host "Step 1: Creating remote directory..." -ForegroundColor Yellow
ssh -p 1414 "root@$DropletIP" "mkdir -p ~/cognitive-engine"

Write-Host "Step 2: Uploading files (config + source only)..." -ForegroundColor Yellow
# Upload config files + source in one scp call
scp -P 1414 -r Dockerfile docker-compose.yml .dockerignore pyproject.toml uv.lock litellm_config.yaml .env src "root@${DropletIP}:~/cognitive-engine/"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upload. Check SSH connection." -ForegroundColor Red
    exit 1
}

# --- Step 3: SSH once to install Docker and deploy ---
Write-Host "Step 3: Deploying on droplet..." -ForegroundColor Yellow
ssh -p 1414 "root@$DropletIP" @"
cd ~/cognitive-engine
# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo 'Installing Docker...'
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=`$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu `$(. /etc/os-release && echo `$VERSION_CODENAME) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo 'Docker installed!'
else
    echo 'Docker already installed.'
fi

# Allow port 8001 through firewall
ufw allow 8001/tcp 2>/dev/null || true

# Deploy
cd ~/cognitive-engine
docker compose down 2>/dev/null || true
docker compose up -d --build 2>&1
echo ''
echo 'Waiting 10s for service to start...'
sleep 10
docker compose ps
echo ''
echo 'Testing health endpoint...'
curl -sf http://localhost:8001/health || echo 'Health check pending — container may still be starting.'
"@

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Service URL: http://$DropletIP:8001" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Test from your browser: http://$DropletIP:8001/health" -ForegroundColor White
Write-Host "2. View logs: ssh -p 1414 root@$DropletIP 'cd cognitive-engine && docker compose logs -f'" -ForegroundColor White
