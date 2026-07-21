# ADR 0003 — JWT access tokens with rotating refresh tokens

## Status
Proposed (stub — to be finalized in Phase 1)

## Context
The platform needs stateless service-to-service auth (gateway validates
requests without calling the identity service) but also immediate revocation
on logout, password change, or token theft.

## Decision
Short-lived JWT access tokens (~15 min: `sub`, `roles`, `exp`, `jti`) paired
with opaque, single-use refresh tokens stored hashed (SHA-256) in the
identity database. Refresh tokens rotate on every use within a `family_id`;
presenting an already-rotated token is treated as theft — the entire family
is revoked and `TOKEN_REUSE_DETECTED` is audit-logged. Password changes
revoke all families.

## Consequences
- Gateway validates JWTs locally; revocation latency is bounded by the
  access-token lifetime.
- Reuse detection contains stolen refresh tokens.
- Open items for Phase 1: token delivery choice for the SPA (httpOnly cookie
  vs response body), signing algorithm/key rotation procedure.
