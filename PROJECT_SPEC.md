# Adhera — Medication Adherence & Caregiver Escalation Platform

Privacy-focused medication adherence platform. Reminds users when medication is due, records confirmations, and escalates to trusted caregivers when a dose goes unconfirmed. Portfolio/educational prototype — **not a certified medical device**. Records user confirmation only; never claims to prove ingestion.

## Core Workflow

1. Dose becomes due → reminder sent
2. User confirms: **Taken / Skipped / Delayed**
3. No response within confirmation window → repeat reminder
4. Still unconfirmed → first caregiver alerted
5. Caregiver acknowledges (or alert escalates to secondary caregiver)
6. Every action recorded in an audit log

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Angular, TypeScript, Angular Material, web push |
| Backend | Python 3.13+, FastAPI, Pydantic, SQLAlchemy 2, Alembic |
| Data | PostgreSQL (per service), Redis, RabbitMQ |
| Workers | Celery + Celery Beat (or DB-backed scheduler) |
| Auth | JWT access + rotating refresh tokens, Argon2 hashing |
| Testing | pytest, pytest-mock, testcontainers, Playwright |
| Tooling | Ruff, mypy/Pyright, Docker Compose, GitHub Actions |
| Security CI | pip-audit, CodeQL/Semgrep, Trivy, gitleaks |

## Architecture

```
Angular Frontend
      |
FastAPI API Gateway (JWT validation, routing, rate limiting, correlation IDs)
      |
      +---------------------------+
      |                           |
Identity & Consent Service   Medication Service
                                  |
                              RabbitMQ
                                  |
                     Notification & Escalation Service
```

- Each service: own Docker container, own PostgreSQL DB/schema (no cross-service table access)
- REST for synchronous calls; RabbitMQ events for async workflows
- Monorepo

### Services

**1. API Gateway** — single entry point, JWT validation, routing, Redis rate limiting, correlation IDs, latency/error logging.
Routes: `/api/{auth,users,caregivers,consents,medications,schedules,doses,alerts,notifications,reports}/**`

**2. Identity & Consent Service** — registration, login, JWT, password reset, profiles, caregiver invitations, granular consent, RBAC, permission audit.
Roles: `PATIENT`, `CAREGIVER`, `ADMIN` (a user can be both patient and caregiver).
Consent scopes (per caregiver): missed-dose alerts, view medication names, view dose history, view adherence summaries, add notes, manage schedules, manage escalation contacts.
Consent record: granted/revoked/expiry dates, scope, grantor, grantee. Revocable at any time.

**3. Medication Service** — medications, schedules, dose-instance generation, dose status, confirmations, time zones/DST, refill reminders, adherence summaries, event publishing.

**4. Notification & Escalation Service** — consumes dose events, sends reminders/repeat reminders, caregiver alerts, tracks delivery + acknowledgements, secondary escalation, retries, dead-letter queue, immutable alert history.
MVP channels: in-app, web push, email. (SMS later.)

## Data Models (key fields)

**Medication**: id, patient_id, name, display_name, dosage_text, instructions, form (`TABLET|CAPSULE|LIQUID|INJECTION|INHALER|PATCH|OTHER`), optional_image_url, active, start/end_date, prescriber_name, pharmacy_name, refill_date, timestamps

**Schedule**: id, medication_id, patient_id, timezone (IANA), schedule_type, scheduled_times, days_of_week, interval_days, confirmation_window_minutes, repeat_reminder_minutes, maximum_repeat_reminders, escalation_enabled, first/second_escalation_delay_minutes, active, timestamps

**DoseInstance**: id, schedule_id, medication_id, patient_id, scheduled_at, status, confirmed_at, confirmation_method, user_note, timestamps
- Statuses: `UPCOMING, DUE, CONFIRMED_TAKEN, CONFIRMED_SKIPPED, CONFIRMED_DELAYED, OVERDUE, CAREGIVER_ALERTED, RESOLVED_BY_CAREGIVER, EXPIRED`
- Confirmation methods: `APP_BUTTON, VOICE, QR_CODE, NFC, CAREGIVER, MANUAL_CORRECTION`

**Alert**: id, dose_instance_id, patient_id, caregiver_id, alert_level, status, channel, sent_at, delivered_at, acknowledged_at, acknowledgement_note, retry_count, timestamps
- Statuses: `PENDING, SENT, DELIVERED, ACKNOWLEDGED, FAILED, ESCALATED, CANCELLED`

## Events (versioned schemas)

All events carry: `event_id` (uuid), `event_type`, `event_version`, `occurred_at`, `correlation_id`.

- **DoseDue** — dose_instance_id, patient_id, medication_id, scheduled_at
- **DoseConfirmed** — dose_instance_id, patient_id, status, confirmation_method
- **DoseConfirmationOverdue** — dose_instance_id, patient_id, scheduled_at, overdue_minutes
- **CaregiverAlerted** — alert_id, dose_instance_id, patient_id, caregiver_id, alert_level
- **AlertAcknowledged** — alert_id, caregiver_id, acknowledgement_note

## Reliability (core engineering focus)

- **Idempotency**: unique event IDs; consumers store processed IDs; idempotency keys on confirmation/acknowledgement endpoints
- **Transactional outbox**: dose update + outbox event committed together; background publisher sends to RabbitMQ
- **Retries**: exponential backoff, max retry count, dead-letter queue, delivery-attempt audit
- **Scheduler recovery**: doses stored in PostgreSQL (no in-memory-only timers); recovery worker finds unprocessed due doses, unescalated overdue doses, unacknowledged alerts, dead Celery tasks
- **Distributed locking**: Redis or PostgreSQL advisory locks — no double-processing of a dose
- **Time zones**: UTC timestamps + per-user IANA timezone; test DST transitions
- **Offline**: cached upcoming doses, locally queued confirmations, sync on reconnect; backend decides timely vs. late; conflicts recorded, not overwritten

Must stay reliable under: duplicate messages, worker crashes, service restarts, notification failures, timezone/DST changes, offline devices, revoked caregiver access, concurrent caregiver responses.

## Security & Privacy

- HTTPS, short-lived JWT + rotating refresh tokens, Argon2
- RBAC + resource-level authorization + granular consent
- Revoked consent blocks access immediately; sessions revoked on password change
- Audit all access to medication/adherence records
- Mask sensitive fields in logs; no medication instructions in request logs
- Rate-limit auth and invitation endpoints
- Secrets via env vars/secret manager; nothing in Git
- Patient data export; soft-delete relationships when audit retention required
- Synthetic data only in demos/tests/repo

## Observability

Structured JSON logs, correlation IDs, OpenTelemetry traces, Prometheus metrics (queue depth, failed notifications, delivery latency, ack latency, recovery count). Endpoints: `/health`, `/ready`, `/metrics`.

## Frontend

**Patient pages**: registration, login, Today dashboard, upcoming doses, medication list/create/edit, schedule editor, dose confirmation, dose history, caregiver management, consent management, notification preferences, adherence report, profile/timezone.

**Caregiver pages**: dashboard, active alerts, alert details, acknowledge alert, patient list, shared dose history, notes, notification preferences.

**Today dashboard** (keep extremely simple): current date, next medication, time remaining, large **Taken** / **Remind me later** / **Skip** buttons, recent confirmations, upcoming doses.

**Accessibility**: large buttons, icons + text labels, high contrast, minimal steps, simple language, no hidden critical actions, confirmation before destructive actions, screen-reader labels, keyboard nav, adjustable text size, reduced motion, never color-only status.

## AI Features (Phase 6 — NOT in MVP)

All AI output requires explicit user approval before activation.

**Allowed**: natural-language → proposed schedule, OCR of prescription labels, voice → reminder, simplify/translate instructions, plain-language adherence summaries, scheduling-conflict detection, dose-history summaries for appointments.

**Prohibited**: recommending/changing dosages, telling patient to stop or double doses, deciding on late doses, diagnosing, interpreting hallucinations/delusions, predicting psychosis, autonomously contacting emergency services, modifying schedules without approval, presenting as a clinician. Missed-dose guidance shows only previously entered human instructions.

## Repository Structure

```
adhera/
├── frontend/angular-app/
├── services/{api-gateway, identity-service, medication-service, notification-service}/
├── shared/{event-schemas, logging, auth, test-utils}/
├── infrastructure/{docker, rabbitmq, monitoring, terraform}/
├── docs/{ARCHITECTURE.md, API.md, USER_GUIDE.md, SECURITY.md, adr/}
├── tests/{integration, contract, end-to-end}/
├── docker-compose.yml
├── pyproject.toml
├── Makefile
└── README.md
```

## Development Phases

- **Phase 0 — Foundation**: monorepo, Docker Compose, Postgres/Redis/RabbitMQ, FastAPI templates, shared config, structured logging, health endpoints, CI (Ruff, types, pytest), architecture docs
- **Phase 1 — Auth & Consent**: registration, login, refresh tokens, roles, caregiver invitations, consent scopes, authorization tests, permission audit
- **Phase 2 — Medication MVP**: medication/schedule CRUD, time zones, dose generation, Today dashboard, confirmations, dose history, scheduling unit tests
- **Phase 3 — Reminders & Escalation**: RabbitMQ publishing, Celery workers, initial/repeat reminders, overdue detection, caregiver alerts, acknowledgement, secondary escalation, DLQs, idempotent consumers
- **Phase 4 — Reliability**: transactional outbox, recovery sweeper, distributed locks, retry policies, failure-simulation/DST/restart/duplicate-message tests
- **Phase 5 — Frontend polish**: accessible dashboards, responsive UI, web push, offline queue, adherence reports, Playwright e2e
- **Phase 6 — AI assistant**: schedule extraction, voice/OCR input, approval screen, weekly summaries, AI audit logs, prompt/model version tracking
- **Phase 7 — Deployment**: cloud deploy, managed Postgres, HTTPS, secrets, monitoring, backup docs, synthetic demo accounts

## MVP Scope

Registration/login (patient + caregiver), JWT auth, roles, medication creation, daily schedules, timezone support, dose generation, initial + repeat reminders, taken/skipped/delayed confirmations, first caregiver escalation, caregiver acknowledgement, dose + alert history, granular consent, PostgreSQL, RabbitMQ events, Redis (rate limiting/locks), Docker Compose, unit + Testcontainers integration tests, Swagger, both Angular dashboards, GitHub Actions security pipeline. **No AI in first milestone.**

## Essential Tests

- **Scheduling**: daily/weekly/monthly generation, multiple daily doses, start/end dates, timezone conversion, DST start/end, schedule modification, deactivated medication
- **Reminders**: sent once, duplicate event ≠ duplicate reminder, repeat after delay, confirmation cancels pending reminders, late confirmation recorded, worker restart loses nothing
- **Escalation**: first caregiver alerted, revoked caregiver not alerted, consent-gated visibility, ack stops escalation, secondary alerted on no-ack, duplicate overdue ≠ duplicate alert, retry flow, DLQ on permanent failure
- **Security**: patient isolation, caregiver sees only approved data, revoked consent blocks immediately, expired token rejected, refresh rotation, rate limiting, no sensitive data in logs

## Acceptance Criteria

1. Patient can register, log in, create medication + schedule
2. Doses generated in correct timezone; due reminder received
3. Patient can confirm/delay/skip; unanswered dose marked overdue
4. Selected caregiver alerted and can acknowledge
5. Duplicate events → no duplicate alerts; restarts don't erase doses
6. Consent rules block unauthorized access; all important actions audited
7. Integration tests run against real Postgres/Redis/RabbitMQ containers
8. One-command local run via Docker Compose; demo uses synthetic data only
9. Swagger per service; GitHub Actions pipeline passes all tests + scans

## Positioning

> Adhera is a privacy-focused medication adherence platform built with Python, FastAPI, Angular, PostgreSQL, Redis, and RabbitMQ. It manages complex medication schedules, records patient confirmations, and uses a reliable event-driven escalation system to notify trusted caregivers when important doses remain unconfirmed.

Pitch: *"I built a Python microservices platform that reliably manages medication reminders and escalates missed confirmations to patient-approved caregivers, even when workers restart, messages are duplicated, or notification delivery temporarily fails."*
