# Contributing to Voco

Thank you for your interest in contributing to Voco! We welcome contributions from the community.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/Voco-ai.git
   cd Voco-ai
   ```
3. **Create a branch** for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### MCP Gateway (Frontend + Tauri)
```bash
cd services/mcp-gateway
bun install
bun run dev
```

### Cognitive Engine (Python Backend)
```bash
cd services/cognitive-engine
uv sync
uv run uvicorn src.main:app --reload --port 8001
```

## Code Style

- **TypeScript/React**: Follow existing patterns. Use functional components with hooks.
- **Rust**: Run `cargo fmt` and `cargo clippy` before committing.
- **Python**: Follow PEP 8. Use type hints. Run `ruff check` before committing.

## Pull Request Process

1. Ensure your code builds and passes all existing tests
2. Update documentation if your change affects public APIs
3. Write a clear PR description explaining:
   - What changed and why
   - How to test the change
   - Any breaking changes
4. Request review from a maintainer
5. Address review feedback promptly

## Commit Messages

Use clear, descriptive commit messages:
```
feat: add sliding window rate limiter middleware
fix: resolve WebSocket reconnection race condition
docs: update API key setup instructions
```

## Reporting Bugs

Use the [Bug Report](https://github.com/Radix-Obsidian/Voco-ai/issues/new?template=bug_report.md) issue template. Include:
- Steps to reproduce
- Expected vs actual behavior
- Platform and version information
- Relevant logs or screenshots

## Feature Requests

Use the [Feature Request](https://github.com/Radix-Obsidian/Voco-ai/issues/new?template=feature_request.md) issue template.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
