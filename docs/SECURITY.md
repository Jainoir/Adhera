# Security

Adhera handles sensitive health-related information. Security requirements:

## Authentication & authorization
- JWT access tokens with short expiration; rotating refresh tokens
- Argon2 password hashing
- Role-based access control (`PATIENT`, `CAREGIVER`, `ADMIN`) plus resource-level authorization
- Granular caregiver consent scopes; revocation takes effect immediately
- Sessions revoked after password changes
- Rate limiting on authentication and invitation endpoints

## Data protection
- HTTPS in all deployed environments
- Encryption at rest where supported
- Credentials via environment variables or a secret manager — never committed to Git
- Sensitive fields masked in logs; medication instructions never appear in ordinary request logs
- Audit log for all access to medication and adherence records
- Soft-delete for sensitive relationships when audit retention is required
- Patients can export their data and revoke caregiver access at any time

## Pipeline checks (GitHub Actions)
- Dependency vulnerability scan (`pip-audit`)
- Static analysis (CodeQL or Semgrep)
- Container scan (Trivy)
- Secret scan (gitleaks)

## Demo data
Only synthetic data in demos, automated tests, and this repository. Never real patient information.
