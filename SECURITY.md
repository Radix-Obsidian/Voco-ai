# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 2.x     | Yes                |
| 1.x     | No                 |

## Reporting a Vulnerability

We take security seriously at Voco. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Email**: Send details to security@voco.ai
2. **Do NOT** open a public GitHub issue for security vulnerabilities
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Resolution Target**: Within 30 days for critical issues

### What to Expect

- We will acknowledge receipt of your report
- We will investigate and validate the issue
- We will work on a fix and coordinate disclosure
- We will credit you in our security advisories (unless you prefer anonymity)

## Security Architecture

Voco is built with a zero-trust architecture:

- **No Direct File Access**: The AI engine (Python) has zero direct access to your filesystem. All file operations go through the Tauri Rust backend with path validation.
- **Human-in-the-Loop**: High-risk commands (git push, database mutations) require explicit user approval before execution.
- **Sandboxed Execution**: All terminal commands run in a scoped sandbox with filesystem boundaries enforced by Tauri's fs_scope.
- **Local-First**: Your source code never leaves your machine. Voice audio is streamed to Deepgram for transcription only.

## Scope

The following are in scope for security reports:

- Path traversal in the MCP Gateway
- Bypass of Human-in-the-Loop approval
- WebSocket injection or manipulation
- Authentication/authorization flaws
- Data exposure or leakage

## Out of Scope

- Denial of service attacks
- Social engineering
- Issues in third-party dependencies (report to the upstream project)
