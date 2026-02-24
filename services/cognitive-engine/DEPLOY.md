# Deploy Cognitive Engine to DigitalOcean Droplet

## Your Droplet Info
- **IP Address**: 146.190.121.108
- **Location**: This guide assumes Ubuntu 22.04 LTS

## Step 1: Prepare Files Locally

1. Copy `.env.production` to `.env` and fill in your API keys:
   ```bash
   cd services/cognitive-engine
   copy .env.production .env
   ```

2. Edit `.env` with your actual API keys (use Notepad or VSCode):
   - ANTHROPIC_API_KEY
   - DEEPGRAM_API_KEY
   - CARTESIA_API_KEY
   - SUPABASE_URL
   - SUPABASE_SERVICE_KEY

## Step 2: Upload Files to Droplet

Open PowerShell and run:

```powershell
# Navigate to your project
cd "C:\Users\autre\Downloads\Voco V2\services"

# Upload the cognitive-engine folder to droplet
scp -r cognitive-engine root@146.190.121.108:~/
```

You'll be prompted for your droplet's root password.

## Step 3: SSH into Droplet

```powershell
ssh root@146.190.121.108
```

## Step 4: Install Docker (if not already installed)

Once logged into the droplet, run:

```bash
# Update system
sudo apt update
sudo apt install -y ca-certificates curl

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

## Step 5: Deploy the Cognitive Engine

```bash
# Navigate to the uploaded folder
cd ~/cognitive-engine

# Build and start the container
docker compose up -d --build

# This will:
# - Build a Docker image from the Dockerfile
# - Start the container in detached mode
# - Expose port 8001
# - Auto-restart if it crashes
```

## Step 6: Verify Deployment

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f

# Test the health endpoint
curl http://localhost:8001/health

# If healthy, you should see: {"status":"ok"}
```

## Step 7: Configure Firewall (if needed)

```bash
# Allow port 8001 through UFW firewall
sudo ufw allow 8001/tcp
sudo ufw status
```

## Step 8: Test from Your Local Machine

From your Windows machine, open PowerShell:

```powershell
# Test the external endpoint
curl http://146.190.121.108:8001/health
```

## Useful Commands

### View Logs
```bash
docker compose logs -f
```

### Restart Service
```bash
docker compose restart
```

### Stop Service
```bash
docker compose down
```

### Rebuild After Code Changes
```bash
# Upload new files first (from Windows):
scp -r cognitive-engine root@146.190.121.108:~/

# Then on droplet:
docker compose down
docker compose up -d --build
```

### Update Environment Variables
```bash
# Edit .env file
nano .env

# Restart to apply changes
docker compose restart
```

## Troubleshooting

### Container Won't Start
```bash
# Check logs for errors
docker compose logs

# Common issues:
# - Missing API keys in .env
# - Port 8001 already in use
# - Out of memory
```

### Can't Connect Externally
```bash
# Check if container is running
docker compose ps

# Check if port is open
sudo ufw status

# Check if service is listening
sudo netstat -tulpn | grep 8001
```

### View Container Resource Usage
```bash
docker stats
```

## Next Steps

Once deployed and verified:
1. Update your desktop app's WebSocket URL to `ws://146.190.121.108:8001/ws/voco-stream`
2. Consider setting up NGINX reverse proxy for HTTPS
3. Set up monitoring (optional)
4. Configure automated backups (optional)
