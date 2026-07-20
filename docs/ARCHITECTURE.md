# Architecture

## Overview

Adhera is a microservices platform: an API gateway plus three backend services, communicating over REST (synchronous) and RabbitMQ events (asynchronous). Each service owns its own PostgreSQL database — no cross-service table access.

```
Angular Frontend
      |
FastAPI API Gateway  (JWT validation, routing, Redis rate limiting, correlation IDs)
      |
      +---------------------------+
      |                           |
Identity & Consent Service   Medication Service
                                  |
                              RabbitMQ
                                  |
                     Notification & Escalation Service
```

## Services

| Service | Responsibility | Port |
|---|---|---|
| api-gateway | Entry point, JWT validation, routing, rate limiting | 8000 |
| identity-service | Users, auth, caregiver relationships, granular consent, RBAC | 8001 |
| medication-service | Medications, schedules, dose generation, confirmations, time zones | 8002 |
| notification-service | Reminders, caregiver alerts, escalation, retries, alert history | 8003 |

## Event flow

1. `medication-service` generates dose instances from schedules (stored in PostgreSQL, never in-memory only).
2. When a dose is due, a `DoseDue` event is written to the **transactional outbox** in the same transaction as the dose update; a background publisher relays it to RabbitMQ.
3. `notification-service` consumes events **idempotently** (processed event IDs are stored) and sends reminders.
4. Unconfirmed doses produce `DoseConfirmationOverdue` → caregiver alert → optional secondary escalation.
5. Confirmations (`DoseConfirmed`) cancel pending reminders and escalations.

Event schemas are versioned JSON Schema documents in [`shared/event-schemas/`](../shared/event-schemas/).

## Reliability mechanisms

- **Transactional outbox** — dose updates and event publication commit atomically
- **Idempotent consumers** — duplicate RabbitMQ deliveries never create duplicate alerts
- **Recovery sweeper** — periodically finds unprocessed due doses, unescalated overdue doses, unacknowledged alerts
- **Distributed locking** — Redis / PostgreSQL advisory locks prevent double-processing
- **Retries** — exponential backoff, max attempts, dead-letter queue, delivery-attempt audit
- **Time zones** — UTC storage + per-user IANA timezone; DST transitions covered by tests

## Decisions

Architecture decision records live in [`adr/`](adr/).
