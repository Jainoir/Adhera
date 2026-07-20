# Adhera — Medication Adherence & Caregiver Escalation Platform

Adhera is a privacy-focused medication adherence platform built with Python, FastAPI, Angular, PostgreSQL, Redis, and RabbitMQ. It manages complex medication schedules, records patient confirmations, and uses a reliable event-driven escalation system to notify trusted caregivers when important doses remain unconfirmed.

> **Note:** Adhera is a portfolio and educational prototype, **not a certified medical device**. It records user confirmations only — it never claims to independently verify medication ingestion.

## Core workflow

1. A dose becomes due → the patient receives a reminder
2. The patient confirms: **Taken / Skipped / Delayed**
3. No response within the confirmation window → repeat reminder
4. Still unconfirmed → the first approved caregiver is alerted
5. No acknowledgement → the alert escalates to a secondary caregiver
6. Every reminder, confirmation, notification, and acknowledgement is audit-logged

## Architecture

```
Angular Frontend
      |
FastAPI API Gateway  (JWT validation, routing, rate limiting, correlation IDs)
      |
      +---------------------------+
      |                           |
Identity & Consent Service   Medication Service
                                  |
                              RabbitMQ
                                  |
                     Notification & Escalation Service
```

- Each service runs in its own container and owns its own PostgreSQL schema
- REST for synchronous calls, RabbitMQ events for async workflows
- Reliability first: transactional outbox, idempotent consumers, recovery sweeper, distributed locking

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the full specification and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design details.

## Getting started

```bash
# Start infrastructure + all services
docker compose up --build

# Run backend tests
make test

# Lint and type-check
make lint
```

| Service | Local port | Docs |
|---|---|---|
| API Gateway | 8000 | http://localhost:8000/docs |
| Identity & Consent | 8001 | http://localhost:8001/docs |
| Medication | 8002 | http://localhost:8002/docs |
| Notification & Escalation | 8003 | http://localhost:8003/docs |

## Repository layout

```
adhera/
├── frontend/angular-app/      # Angular patient + caregiver UI
├── services/                  # FastAPI microservices
│   ├── api-gateway/
│   ├── identity-service/
│   ├── medication-service/
│   └── notification-service/
├── shared/                    # Event schemas, logging, auth, test utilities
├── infrastructure/            # Docker, RabbitMQ, monitoring, Terraform
├── docs/                      # Architecture, API, security docs, ADRs
└── tests/                     # Integration, contract, and end-to-end tests
```

## Development phases

| Phase | Focus |
|---|---|
| 0 | Foundation — monorepo, Docker Compose, CI, service templates |
| 1 | Authentication & granular caregiver consent |
| 2 | Medication & schedule CRUD, dose generation, Today dashboard |
| 3 | Reminders, overdue detection, caregiver escalation |
| 4 | Reliability — outbox, recovery sweeper, locking, failure tests |
| 5 | Frontend polish, offline queue, web push, Playwright e2e |
| 6 | Human-approved AI assistance |
| 7 | Cloud deployment |

## License

MIT
