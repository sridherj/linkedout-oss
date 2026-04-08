# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do NOT file public issues for security vulnerabilities.**

Use [GitHub Security Advisories](https://github.com/sridherj/linkedout-oss/security/advisories/new) to report vulnerabilities. Security advisories are private by default, ensuring responsible disclosure.

### Response SLA

- **Acknowledgment:** Within 72 hours of report submission
- **Critical patches:** Within 30 days of confirmed critical vulnerability

### What to Include

When reporting, please provide:

- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested fix (if any)

## Scope

### In Scope

- Database credential exposure or leaks
- Data leaks between tenants or to unauthorized parties
- SQL injection or other injection attacks
- Unauthorized access to stored LinkedIn data
- API key exposure through logs or error messages

### Out of Scope

- Issues that require physical access to the user's machine
- Local-only tool behavior where the user is the sole operator
- Vulnerabilities in upstream dependencies (report those to the respective projects)

## Security Considerations

LinkedOut is a **local-first** application. The threat model assumes the user trusts their own machine:

- The database runs locally and is not exposed to the network by default
- The backend API (when running) binds to `localhost` only
- API keys and secrets are stored in `~/linkedout-data/config/secrets.yaml` with `chmod 600` permissions
- No data is sent to external services unless explicitly configured (e.g., OpenAI API for optional embeddings)

Users are responsible for:

- Keeping their `~/linkedout-data/config/secrets.yaml` file permissions restricted (`chmod 600`)
- Not exposing the local API port to untrusted networks
- Reviewing Chrome extension permissions before installation
