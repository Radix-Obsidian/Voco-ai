# Voco Cognitive Engine - Quick Deploy Script for Windows
# Run this from: C:\Users\autre\Downloads\Voco V2\services\cognitive-engine

param(
    [string]$DropletIP = "146.190.121.108"
)

$SSH_OPTS = "-o ConnectTimeout=15 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=3"

Write-Host "=== Voco Cognitive Engine Deployment ===" -ForegroundColor Green
Write-Host "Droplet IP: $DropletIP" -ForegroundColor Cyan
Write-Host ""

# --- Pre-flight: Check .env exists ---
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please copy .env.production to .env and add your API keys first:" -ForegroundColor Yellow
    Write-Host "  copy .env.production .env" -ForegroundColor Yellow
    Write-Host "  notepad .env" -ForegroundColor Yellow
    exit 1
}

# --- Pre-flight: Test SSH connectivity ---
Write-Host "Pre-flight: Testing SSH connection..." -ForegroundColor Yellow
$sshTest = ssh $SSH_OPTS.Split(' ') "root@$DropletIP" "echo SSH_OK" 2>&1
if ($sshTest -notmatch "SSH_OK") {
    Write-Host "ERROR: Cannot SSH into droplet." -ForegroundColor Red
    Write-Host "Output: $sshTest" -ForegroundColor Red
    Write-Host ""
    Write-Host "Fix: Add your SSH key via DigitalOcean console:" -ForegroundColor Yellow
    Write-Host "  1. Go to cloud.digitalocean.com > Droplets > voco-engine-prod-v2 > Console" -ForegroundColor White
    Write-Host "  2. Paste: cat >> ~/.ssh/authorized_keys << 'EOF'" -ForegroundColor White
    Write-Host "     <your public key from ~/.ssh/id_rsa.pub>" -ForegroundColor White
    Write-Host "     EOF" -ForegroundColor White
    exit 1
}
Write-Host "  SSH connection OK!" -ForegroundColor Green

# --- Step 1: Create remote directory ---
Write-Host "Step 1: Creating remote directory..." -ForegroundColor Yellow
ssh $SSH_OPTS.Split(' ') "root@$DropletIP" "mkdir -p ~/cognitive-engine"

# --- Step 2: Upload only the files Docker needs ---
Write-Host "Step 2: Uploading files (config + source only)..." -ForegroundColor Yellow
scp -o ConnectTimeout=15 -o StrictHostKeyChecking=no -r Dockerfile docker-compose.yml docker-compose.prod.yml .dockerignore pyproject.toml uv.lock litellm_config.yaml .env nginx src "root@${DropletIP}:~/cognitive-engine/"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upload files. Check SSH connection." -ForegroundColor Red
    exit 1
}
Write-Host "  Upload complete!" -ForegroundColor Green

# --- Step 2b: Fix Windows CRLF line endings in .env on the remote ---
Write-Host "Step 2b: Fixing .env line endings on remote..." -ForegroundColor Yellow
ssh $SSH_OPTS.Split(' ') "root@$DropletIP" "cd ~/cognitive-engine && sed -i 's/\r$//' .env && grep -q '^DOMAIN=' .env || echo 'DOMAIN=api.itsvoco.com' >> .env && grep -q '^CERTBOT_EMAIL=' .env || echo 'CERTBOT_EMAIL=Architect@viperbyproof.com' >> .env"

# --- Step 3: SSH once to install Docker and deploy ---
Write-Host "Step 3: Deploying on droplet (this may take a few minutes on first run)..." -ForegroundColor Yellow
ssh $SSH_OPTS.Split(' ') "root@$DropletIP" @"
set -e
cd ~/cognitive-engine

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo '>>> Installing Docker...'
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=`$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu `$(. /etc/os-release && echo `$VERSION_CODENAME) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo '>>> Docker installed!'
else
    echo '>>> Docker already installed.'
fi

# Allow port 8001 through firewall
ufw allow 8001/tcp 2>/dev/null || true

# Stop any existing deployment (try prod compose first, then basic)
echo '>>> Stopping existing containers...'
cd ~/cognitive-engine
docker compose -f docker-compose.prod.yml down 2>/dev/null || docker compose down 2>/dev/null || true

# Build and deploy with prod compose (nginx + TLS)
echo '>>> Building and starting containers (prod — nginx + TLS)...'
docker compose -f docker-compose.prod.yml up -d --build 2>&1

# Wait and verify
echo ''
echo '>>> Waiting 15s for service to start...'
sleep 15

echo '>>> Container status:'
docker compose -f docker-compose.prod.yml ps

echo ''
echo '>>> Health check:'
curl -sf http://localhost:8001/health && echo '' || echo 'Health check pending — container may still be starting. Check logs with: docker compose -f docker-compose.prod.yml logs -f'
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "WARNING: Remote deployment commands returned an error. Check output above." -ForegroundColor Yellow
    Write-Host "SSH into droplet to debug: ssh root@$DropletIP" -ForegroundColor Yellow
    Write-Host "View logs: ssh root@$DropletIP 'cd cognitive-engine && docker compose logs'" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Service URL: http://$DropletIP:8001" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  Test health:  curl http://$DropletIP:8001/health" -ForegroundColor White
Write-Host "  View logs:    ssh root@$DropletIP 'cd cognitive-engine && docker compose logs -f'" -ForegroundColor White
Write-Host "  Restart:      ssh root@$DropletIP 'cd cognitive-engine && docker compose restart'" -ForegroundColor White
