# API

Each service exposes Swagger/OpenAPI docs at `/docs`. Gateway routes:

```
/api/auth/**
/api/users/**
/api/caregivers/**
/api/consents/**
/api/medications/**
/api/schedules/**
/api/doses/**
/api/alerts/**
/api/notifications/**
/api/reports/**
```

## Conventions

These apply to every endpoint on every service.

### Error envelope

All error responses (4xx/5xx) use one shape:

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "Human-readable summary, safe to show to users.",
    "correlation_id": "0b96…",
    "details": [
      {"field": "scheduled_times", "issue": "must be HH:MM local time"}
    ]
  }
}
```

- `code` is a stable, machine-readable snake_case identifier.
- `details` is optional; used for validation errors (one entry per field).
- Bodies never include stack traces, SQL, or internal hostnames.

### Correlation IDs

- Every request may send `X-Correlation-ID`; the gateway generates a UUID if
  absent and propagates it to downstream calls, logs, and events.
- Every response echoes `X-Correlation-ID`. Clients should surface it in
  error toasts so support can find the trace.

### Idempotency keys

- Every state-changing endpoint on doses and alerts (e.g.
  `POST /doses/{id}/confirm`, `POST /alerts/{id}/acknowledge`) accepts an
  `Idempotency-Key` header (client-generated UUID).
- Replaying a request with the same key returns the **original** result with
  no additional state change — safe for offline queues and retries.
- Keys are scoped per endpoint + authenticated user.

### Pagination

List endpoints accept `limit` (default 50, max 200) and `offset` (default 0)
and respond with:

```json
{"items": [], "total": 123, "limit": 50, "offset": 0}
```

### Observability endpoints

Every service (behind the gateway or directly in development) exposes:

| Endpoint | Purpose |
|---|---|
| `/health` | Liveness — process is up |
| `/ready` | Readiness — pings own DB/Redis/RabbitMQ; 503 + per-dependency status map on failure |
| `/metrics` | Prometheus metrics |
