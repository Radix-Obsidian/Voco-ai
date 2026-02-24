# Voco v2.0.0 — Enterprise Distribution Release 🚀

## 🌟 Highlights

- **Enterprise-Grade Distribution** via CrabNebula Cloud CDN
- **Tier-Gated Release Channels** powered by Keygen.sh
- **Zero-Trust Security** with cryptographic update signing
- **Cross-Platform Support** for Windows, macOS, and Linux

## 🔐 Security & Updates

- **Auto-Updates**: Seamless in-app updates via CrabNebula CDN
- **Cryptographic Signing**: All updates are signed and verified
- **Zero-Trust Model**: All file operations go through Tauri sandbox
- **HITL Approval**: Human-in-the-loop for high-risk operations

## 🎯 Release Channels

| Tier | Channel | Update Delay | Price |
|------|---------|--------------|-------|
| Architect | nightly | Immediate | $149/mo |
| Orchestrator | beta | 48h after nightly | $39/mo |
| Listener | stable | 1 week after beta | Free |

## 🛠️ Technical Improvements

- Added `tauri-plugin-updater` for secure auto-updates
- Added `tauri-plugin-dialog` for native update prompts
- Added Keygen.sh license validation + tier resolution
- Added GitHub Actions release automation
- Configured CrabNebula Cloud CDN endpoints

## 🔍 Under the Hood

- **Build System**: Tauri v2 + Rust + React/Vite
- **Update Protocol**: Signed JSON manifests via CrabNebula CDN
- **License Validation**: Keygen.sh REST API with offline caching
- **CI/CD**: GitHub Actions matrix builds (Win/Mac/Linux)

## 📦 Installation

Download the appropriate installer for your platform:
- Windows: `Voco_2.0.0_x64_en-US.msi`
- macOS: `Voco_2.0.0_x64.dmg`
- Linux: `voco_2.0.0_amd64.deb` or `Voco_2.0.0_x64.AppImage`

## 🔄 Upgrading

Existing installations will receive the update automatically based on tier:
1. Architect users: Available immediately
2. Orchestrator users: Available in 48 hours
3. Listener users: Available in 1 week

## 🐛 Known Issues

None reported. This is a major infrastructure release focused on distribution.

## 🙏 Credits

- [CrabNebula Cloud](https://crabnebula.dev) for enterprise CDN
- [Keygen.sh](https://keygen.sh) for license management
- [Tauri](https://tauri.app) core team for updater plugin
