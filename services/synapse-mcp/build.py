"""Build script to create standalone synapse-mcp executable for Tauri bundling.

This script uses PyInstaller to create a single-file executable that can be
bundled with the Tauri desktop app, eliminating the need for users to install Python.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Determine platform-specific executable name
SYSTEM = platform.system()
if SYSTEM == "Windows":
    BINARY_NAME = "synapse-mcp.exe"
elif SYSTEM == "Darwin":
    BINARY_NAME = "synapse-mcp-macos"
else:  # Linux
    BINARY_NAME = "synapse-mcp-linux"

# Paths
PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
TAURI_BINARIES = PROJECT_ROOT.parent / "mcp-gateway" / "src-tauri" / "binaries"

def clean():
    """Remove previous build artifacts."""
    print("🧹 Cleaning previous build artifacts...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    
    # Remove spec file if it exists
    spec_file = PROJECT_ROOT / "server.spec"
    if spec_file.exists():
        spec_file.unlink()

def build_executable():
    """Build standalone executable using PyInstaller."""
    print(f"🔨 Building standalone executable for {SYSTEM}...")
    
    pyinstaller_args = [
        "pyinstaller",
        "--onefile",  # Single executable file
        "--name", "synapse-mcp",
        "--clean",
        "--noconfirm",
        str(SRC_DIR / "server.py"),
    ]
    
    # Add platform-specific optimizations
    if SYSTEM == "Windows":
        pyinstaller_args.extend([
            "--console",  # Keep console for stderr logging
            "--icon", "NONE",
        ])
    
    result = subprocess.run(pyinstaller_args, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print("❌ Build failed!")
        sys.exit(1)
    
    print("✅ Build successful!")

def copy_to_tauri():
    """Copy the built executable to Tauri's binaries directory."""
    print(f"📦 Copying executable to Tauri binaries...")
    
    # Ensure Tauri binaries directory exists
    TAURI_BINARIES.mkdir(parents=True, exist_ok=True)
    
    # Find the built executable
    built_exe = DIST_DIR / ("synapse-mcp.exe" if SYSTEM == "Windows" else "synapse-mcp")
    if not built_exe.exists():
        print(f"❌ Built executable not found at {built_exe}")
        sys.exit(1)
    
    # Copy to Tauri binaries with platform-specific name
    target_path = TAURI_BINARIES / BINARY_NAME
    shutil.copy2(built_exe, target_path)
    
    # Make executable on Unix systems
    if SYSTEM != "Windows":
        os.chmod(target_path, 0o755)
    
    print(f"✅ Copied to {target_path}")

def main():
    print("🚀 Building Voco Synapse MCP Server")
    print(f"   Platform: {SYSTEM}")
    print(f"   Binary: {BINARY_NAME}")
    print()
    
    clean()
    build_executable()
    copy_to_tauri()
    
    print()
    print("✨ Build complete!")
    print(f"   Binary location: {TAURI_BINARIES / BINARY_NAME}")
    print()
    print("Next steps:")
    print("  1. Update tauri.conf.json to include the binary in externalBin")
    print("  2. Update voco-mcp.json to use the bundled binary path")

if __name__ == "__main__":
    main()
