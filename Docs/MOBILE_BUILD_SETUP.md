# Voco Mobile Build Setup

This document describes the setup required for iOS and Android mobile builds in the CrabNebula CI pipeline.

## Overview

Our GitHub Actions workflow now supports:
- Windows, macOS, Linux desktop builds (as before)
- Android builds
- iOS builds

All builds are automatically uploaded to CrabNebula Cloud and published under the appropriate release.

## Required GitHub Secrets

### Existing Secrets (Desktop Builds)
- `CN_API_KEY`: The CrabNebula Cloud API key
- `TAURI_SIGNING_PRIVATE_KEY`: The private key used to sign updates
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`: The password for the private key

### New Secrets (Mobile Builds)

#### Android
- `ANDROID_KEY_ALIAS`: The alias for your Android signing keystore
- `ANDROID_KEY_PASSWORD`: The password for your Android signing keystore
- `ANDROID_KEY_BASE64`: Base64-encoded Android keystore file (.jks file)

#### iOS
- `APPLE_API_KEY_ID`: The ID of your App Store Connect API key
- `APPLE_API_KEY`: The private key content for App Store Connect
- `APPLE_API_ISSUER`: The issuer ID for your App Store Connect API key
- `APPLE_DEVELOPMENT_TEAM`: Your Apple development team ID

## How to Generate Mobile Secrets

### Android Keystore Setup

1. Generate a keystore file:

```bash
keytool -genkey -v -keystore voco-android.keystore -alias voco -keyalg RSA -keysize 2048 -validity 10000
```

2. Base64-encode the keystore file:

```bash
base64 voco-android.keystore
```

3. Add the secrets to GitHub:
   - `ANDROID_KEY_ALIAS`: "voco" (or whatever alias you used)
   - `ANDROID_KEY_PASSWORD`: (the password you entered during keystore creation)
   - `ANDROID_KEY_BASE64`: (the output of the base64 command)

### iOS App Store Connect Setup

1. Create an App Store Connect API key in the [Apple Developer portal](https://appstoreconnect.apple.com/access/api)
2. Download the `.p8` private key file
3. Add the secrets to GitHub:
   - `APPLE_API_KEY_ID`: Key ID shown in the App Store Connect
   - `APPLE_API_KEY`: Contents of the `.p8` file
   - `APPLE_API_ISSUER`: Issuer ID shown in App Store Connect
   - `APPLE_DEVELOPMENT_TEAM`: Your Team ID from Apple Developer portal

## Testing Mobile Builds Locally

### Android

Prerequisites:
- Android SDK
- Android NDK
- Java Development Kit (JDK) 17

```bash
rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android
cd services/mcp-gateway
npx tauri android build
```

### iOS

Prerequisites:
- Xcode
- Apple Developer account

```bash
rustup target add aarch64-apple-ios
cd services/mcp-gateway
npx tauri ios build
```

## CrabNebula Cloud Distribution

The same CrabNebula endpoints now serve both desktop and mobile builds. The endpoint in `tauri.conf.json` is correctly configured:

```json
"endpoints": [
  "https://cdn.crabnebula.app/update/radix-obsidian/voco/{{target}}-{{arch}}/{{current_version}}"
],
```

This endpoint follows CrabNebula's recommended pattern and will work for all platforms.
