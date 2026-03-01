#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Downloads the uv standalone binary and places it in the Tauri resources
    directory so the app can manage Python + deps without requiring the user
    to install anything.

.DESCRIPTION
    For the beta installer, we bundle `uv` (~30 MB) which handles:
      1. Auto-downloading Python 3.12 on first launch
      2. Creating a virtual-env and installing cognitive-engine deps
      3. Running uvicorn to start the backend

    This keeps the installer small (~30 MB for uv vs ~400 MB for a full
    Python + venv bundle) while still being zero-friction for non-tech users.

.NOTES
    Run from the monorepo root:  pwsh scripts/bundle-python.ps1
#>

param(
    [string]$UvVersion = "0.6.6",
    [string]$TargetDir = "$PSScriptRoot/../services/mcp-gateway/src-tauri/resources/uv"
)

$ErrorActionPreference = "Stop"

# Determine platform + arch
$os   = if ($IsWindows -or $env:OS -eq "Windows_NT") { "windows" } elseif ($IsMacOS) { "macos" } else { "linux" }
$arch = if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq "Arm64") { "aarch64" } else { "x86_64" }

# Map to uv release asset names
$assetMap = @{
    "windows-x86_64"  = "uv-x86_64-pc-windows-msvc.zip"
    "windows-aarch64"  = "uv-aarch64-pc-windows-msvc.zip"
    "macos-x86_64"    = "uv-x86_64-apple-darwin.tar.gz"
    "macos-aarch64"   = "uv-aarch64-apple-darwin.tar.gz"
    "linux-x86_64"    = "uv-x86_64-unknown-linux-musl.tar.gz"
    "linux-aarch64"   = "uv-aarch64-unknown-linux-musl.tar.gz"
}

$key = "$os-$arch"
$asset = $assetMap[$key]
if (-not $asset) {
    Write-Error "Unsupported platform: $key"
    exit 1
}

$downloadUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/$asset"
$targetDir = Resolve-Path -Path $TargetDir -ErrorAction SilentlyContinue
if (-not $targetDir) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    $targetDir = Resolve-Path -Path $TargetDir
}

$tempFile = Join-Path ([System.IO.Path]::GetTempPath()) $asset

Write-Host "[bundle-python] Downloading uv $UvVersion for $key..."
Write-Host "[bundle-python] URL: $downloadUrl"

Invoke-WebRequest -Uri $downloadUrl -OutFile $tempFile -UseBasicParsing

Write-Host "[bundle-python] Extracting to $targetDir..."

if ($asset.EndsWith(".zip")) {
    Expand-Archive -Path $tempFile -DestinationPath $targetDir -Force
    # The zip extracts into a subdirectory — flatten it
    $subDir = Get-ChildItem -Path $targetDir -Directory | Where-Object { $_.Name -like "uv-*" } | Select-Object -First 1
    if ($subDir) {
        Get-ChildItem -Path $subDir.FullName | Move-Item -Destination $targetDir -Force
        Remove-Item -Path $subDir.FullName -Recurse -Force
    }
} else {
    # tar.gz
    tar -xzf $tempFile -C $targetDir --strip-components=1
}

Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue

# Verify
$uvBin = if ($os -eq "windows") { Join-Path $targetDir "uv.exe" } else { Join-Path $targetDir "uv" }
if (Test-Path $uvBin) {
    $version = & $uvBin --version 2>&1
    Write-Host "[bundle-python] Successfully bundled: $version"
    Write-Host "[bundle-python] Binary at: $uvBin"
} else {
    Write-Error "[bundle-python] uv binary not found at $uvBin after extraction!"
    exit 1
}

# Also copy the cognitive-engine source into resources for release builds
$engineSrc = "$PSScriptRoot/../services/cognitive-engine"
$engineDest = "$PSScriptRoot/../services/mcp-gateway/src-tauri/resources/cognitive-engine"

if (Test-Path $engineSrc) {
    Write-Host "[bundle-python] Copying cognitive-engine source to resources..."

    # Create destination
    New-Item -ItemType Directory -Path $engineDest -Force | Out-Null

    # Copy essential files only (skip .venv, __pycache__, .git)
    $items = @("src", "pyproject.toml", "uv.lock", ".env", ".env.example", "litellm_config.yaml")
    foreach ($item in $items) {
        $srcPath = Join-Path $engineSrc $item
        if (Test-Path $srcPath) {
            $destPath = Join-Path $engineDest $item
            if ((Get-Item $srcPath).PSIsContainer) {
                Copy-Item -Path $srcPath -Destination $destPath -Recurse -Force
            } else {
                Copy-Item -Path $srcPath -Destination $destPath -Force
            }
        }
    }

    # Remove __pycache__ directories
    Get-ChildItem -Path $engineDest -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

    Write-Host "[bundle-python] Cognitive-engine source copied."
}

Write-Host ""
Write-Host "[bundle-python] Done! Resources ready for Tauri build."
Write-Host "[bundle-python] Next: run 'npm run build' or 'npx tauri build' in services/mcp-gateway/"
