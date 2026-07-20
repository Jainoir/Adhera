# Adhera — Implementation Roadmap (Phases 0–7)

This roadmap turns [PROJECT_SPEC.md](../PROJECT_SPEC.md) into an ordered, end-to-end task checklist. Work the phases in order; each phase lists its goal, prerequisites, tasks, and a Definition of Done tied to the spec's acceptance criteria and essential tests.

**Ground rules that apply to every phase:**

- **No AI features before Phase 6.** Phases 0–5 must contain zero LLM/OCR/voice-AI code paths.
- All timestamps are stored in **UTC**; every user and schedule carries an **IANA timezone**; local-time math uses `zoneinfo`.
- Every request carries a **correlation ID** (`X-Correlation-ID`), generated at the gateway if absent, propagated to logs, events, and downstream calls.
- Every state-changing endpoint on doses/alerts accepts an **`Idempotency-Key`** header.
- Every access to medication/adherence data and every consent/permission change is **audit-logged**.
- **Synthetic data only** — no real names, emails, or medications in seeds, tests, or the repo.
- Legend: **(stretch)** = optional for the portfolio milestone; skip without breaking acceptance criteria.

---

## Phase 0 — Foundation Completion

**Goal:** Finish the platform skeleton so every later phase only adds features: shared config/logging/auth libraries, Alembic wiring, real readiness checks, correlation IDs, test harness with Testcontainers, and a CI pipeline that lints, type-checks, tests, and scans.

**Prerequisites:** Current repo state (service skeletons, Compose, event schemas, basic CI).

### Tasks

- [ ] **Shared config base** — `shared/config/__init__.py` (add package): `BaseServiceSettings` (pydantic-settings) with `service_name`, `database_url`, `redis_url`, `rabbitmq_url`, `log_level`, `environment`; refactor each `services/*/app/config.py` to subclass it. Update `.env.example` with every variable.
- [ ] **Structured logging** — implement `shared/logging/__init__.py`: `structlog` JSON logs with `timestamp`, `level`, `service`, `correlation_id`, `event`; a `mask_sensitive()` processor that redacts `password`, `token`, `authorization`, and medication `instructions`/`user_note` fields. Call `configure_logging(settings)` in each `app/main.py`.
- [ ] **Correlation ID middleware** — `shared/logging/middleware.py`: ASGI middleware reading/creating `X-Correlation-ID`, binding it to structlog contextvars and echoing it in responses. Register in all four services.
- [ ] **Database layer per service** — for identity/medication/notification services: `app/db.py` (async engine, `async_session` factory, `Base` declarative base), and Alembic scaffolding: `alembic.ini`, `alembic/env.py` (async, reads `DATABASE_URL`), `alembic/versions/` (replace `.gitkeep`). Add `alembic upgrade head` to service startup (entrypoint script or `make migrate`).
- [ ] **Real readiness checks** — extend `/ready` in each service to ping its DB (`SELECT 1`), Redis, and RabbitMQ (where configured); return 503 with a per-dependency status map when any fails.
- [ ] **Metrics endpoint** — add `prometheus-fastapi-instrumentator` (or `prometheus-client`) to each service; expose `/metrics` with default HTTP latency/error metrics. Custom business metrics come in Phase 4.
- [ ] **Event schema loader** — `shared/event-schemas/__init__.py` + `shared/event_schemas.py` helper: load and validate payloads against the versioned JSON Schemas (`dose_due.v1.json`, etc.); shared Pydantic envelope model `EventEnvelope` (`event_id`, `event_type`, `event_version`, `occurred_at`, `correlation_id`, `payload`).
- [ ] **Test harness** — `shared/test-utils/` package: Testcontainers fixtures for Postgres, Redis, RabbitMQ (`postgres_container`, `redis_container`, `rabbitmq_container`), plus an `async_client` factory for FastAPI apps. Root `tests/integration/conftest.py` wires them. Add one smoke integration test: each service boots, `/health` and `/ready` return 200 against real containers.
- [ ] **CI hardening** — `.github/workflows/ci.yml`: add mypy (or Pyright) job, integration-test job (services: docker), Trivy image scan **(stretch until Phase 7)**, keep Ruff/pytest/pip-audit/gitleaks. Add `make lint`, `make typecheck`, `make test`, `make test-integration`, `make up`, `make migrate` targets to `Makefile`.
- [ ] **Docs** — update `docs/ARCHITECTURE.md` with the outbox/consumer/sweeper sequence diagrams (text/mermaid); add `docs/adr/0002-transactional-outbox.md`, `docs/adr/0003-jwt-refresh-rotation.md` stubs; start `docs/API.md` conventions section (error envelope, correlation ID, idempotency keys, pagination).

### Definition of done

- `docker compose up --build` starts infra + 4 services; all `/health`, `/ready`, `/metrics` respond.
- `make lint`, `make typecheck`, `make test` pass locally and in CI; one Testcontainers smoke test green.
- Logs are structured JSON with correlation IDs; secrets only in env vars.

---

## Phase 1 — Auth & Consent (Identity Service + Gateway)

**Goal:** Full authentication (register/login/refresh/logout with rotating refresh tokens, Argon2), roles, caregiver invitations, granular consent scopes with immediate revocation, permission audit, and gateway JWT validation + rate limiting.

**Prerequisites:** Phase 0 complete (DB layer, Alembic, shared config/logging, test harness).

### Tasks — identity-service data model

- [ ] `services/identity-service/app/models/user.py` — `users`: `id` (uuid pk), `email` (unique, citext/lower-indexed), `password_hash` (Argon2id via `argon2-cffi`), `full_name`, `timezone` (IANA string, default `UTC`), `roles` (array or join table: `PATIENT|CAREGIVER|ADMIN`; a user may hold both), `is_active`, `password_changed_at`, timestamps.
- [ ] `app/models/refresh_token.py` — `refresh_tokens`: `id`, `user_id` (fk), `token_hash` (sha256 of opaque token), `family_id` (uuid, rotation family), `issued_at`, `expires_at`, `revoked_at`, `replaced_by_id`. Index on `token_hash`.
- [ ] `app/models/caregiver.py` — `caregiver_invitations`: `id`, `patient_id`, `invitee_email`, `token_hash`, `status` (`PENDING|ACCEPTED|EXPIRED|CANCELLED`), `expires_at`, timestamps. `caregiver_relationships`: `id`, `patient_id`, `caregiver_id`, `status` (`ACTIVE|REVOKED`), `escalation_priority` (int: 1 = first, 2 = secondary), `revoked_at` (soft delete — never hard-delete while audit retention applies), timestamps. Unique `(patient_id, caregiver_id)`.
- [ ] `app/models/consent.py` — `consents`: `id`, `relationship_id` (fk), `scope` (enum: `MISSED_DOSE_ALERTS`, `VIEW_MEDICATION_NAMES`, `VIEW_DOSE_HISTORY`, `VIEW_ADHERENCE_SUMMARIES`, `ADD_NOTES`, `MANAGE_SCHEDULES`, `MANAGE_ESCALATION_CONTACTS`), `granted_at`, `granted_by` (user id), `revoked_at`, `expires_at`. Unique active `(relationship_id, scope)`.
- [ ] `app/models/audit.py` — `permission_audit`: `id`, `actor_user_id`, `action` (e.g. `CONSENT_GRANTED`, `CONSENT_REVOKED`, `LOGIN`, `TOKEN_REUSE_DETECTED`, `INVITATION_SENT`), `target_user_id`, `resource_type`, `resource_id`, `correlation_id`, `ip_address`, `created_at`. Append-only (no update/delete paths).
- [ ] Alembic migration `0001_initial_identity` covering all of the above.

### Tasks — identity-service API

- [ ] `app/security/passwords.py` (Argon2 hash/verify), `app/security/jwt.py` (issue/verify access tokens: `sub`, `roles`, `exp` ≈ 15 min, `jti`), `app/security/refresh.py` (opaque token generation, rotation, **reuse detection**: presenting a revoked/rotated token revokes the entire family and audit-logs `TOKEN_REUSE_DETECTED`).
- [ ] `app/api/auth.py` — `POST /auth/register` (patient or caregiver role selection), `POST /auth/login` (returns access + refresh; document delivery choice in ADR 0003), `POST /auth/refresh` (rotate), `POST /auth/logout` (revoke family), `POST /auth/password-reset/request` + `POST /auth/password-reset/confirm` (email token; dev email via Mailpit — see Phase 3), password change revokes all refresh-token families (spec: sessions revoked on password change).
- [ ] `app/api/users.py` — `GET /users/me`, `PATCH /users/me` (name, timezone), `GET /users/me/export` **(stretch until Phase 5)**.
- [ ] `app/api/caregivers.py` — `POST /caregivers/invitations` (patient invites by email; rate-limited), `POST /caregivers/invitations/{token}/accept`, `GET /caregivers` (patient view + caregiver's patient list via `GET /caregivers/patients`), `DELETE /caregivers/{relationship_id}` (soft-revoke; cascades consent revocation), `PATCH /caregivers/{relationship_id}` (escalation priority).
- [ ] `app/api/consents.py` — `GET /consents?relationship_id=`, `POST /consents` (grant scope), `DELETE /consents/{id}` (revoke — effective immediately), all writes audit-logged.
- [ ] `app/api/internal.py` — service-to-service endpoints (network-internal, shared-secret header `X-Internal-Token`): `GET /internal/consents/check?patient_id=&caregiver_id=&scope=` (authoritative, no caching beyond ≤30 s TTL so revocation is effectively immediate), `GET /internal/patients/{id}/escalation-contacts` (ordered caregivers holding `MISSED_DOSE_ALERTS`), `GET /internal/users/{id}` (email, timezone, display name for notifications).
- [ ] Shared auth dependency — `shared/auth/__init__.py`: `get_current_user` FastAPI dependency validating JWTs, `require_roles(...)`, reusable in all services.

### Tasks — API gateway

- [ ] `services/api-gateway/app/middleware/auth.py` — validate JWT on all `/api/**` routes except `/api/auth/**`; attach `X-User-Id`, `X-User-Roles` headers to proxied requests.
- [ ] `app/middleware/rate_limit.py` — Redis sliding-window limiter; strict limits on `POST /api/auth/login`, `/api/auth/register`, `/api/auth/password-reset/*`, `/api/caregivers/invitations` (e.g., 5/min/IP + per-account); `429` with `Retry-After`.
- [ ] `app/api/proxy.py` — httpx-based reverse proxy routing `/api/auth|users|caregivers|consents/**` → identity, `/api/medications|schedules|doses|reports/**` → medication, `/api/alerts|notifications/**` → notification; forwards correlation ID; logs method, path, status, latency (no bodies).

### Tasks — tests (security set, part 1)

- [ ] Unit: Argon2 hashing, JWT expiry/claims, refresh rotation state machine, reuse detection revokes family.
- [ ] Integration (Testcontainers): register → login → refresh → logout; expired access token rejected (401); reused rotated refresh token rejected and family revoked; rate limiting returns 429; invitation accept creates relationship; consent grant/revoke lifecycle; `internal/consents/check` flips to deny immediately after revoke; audit rows written for each consent change; **no password/token values appear in captured logs**.

### Definition of done

- Patient and caregiver can register, log in, invite/accept, grant and revoke scoped consent — all via Swagger through the gateway.
- Security tests above pass in CI; auth endpoints are rate limited; every permission change is audited.

---

## Phase 2 — Medication MVP (Medication Service + Angular Skeleton)

**Goal:** Medication and schedule CRUD, timezone-correct dose-instance generation persisted in PostgreSQL, confirmation endpoints with idempotency, dose history, and a minimal Angular app with login + Today dashboard.

**Prerequisites:** Phase 1 (auth for protected endpoints, consent-check internal API).

### Tasks — medication-service data model

- [ ] `services/medication-service/app/models/medication.py` — `medications`: `id`, `patient_id`, `name`, `display_name`, `dosage_text`, `instructions`, `form` (enum `TABLET|CAPSULE|LIQUID|INJECTION|INHALER|PATCH|OTHER`), `optional_image_url`, `active`, `start_date`, `end_date`, `prescriber_name`, `pharmacy_name`, `refill_date`, timestamps.
- [ ] `app/models/schedule.py` — `schedules`: `id`, `medication_id`, `patient_id`, `timezone` (IANA), `schedule_type` (enum `DAILY|WEEKLY|INTERVAL`; `MONTHLY` **(stretch)**), `scheduled_times` (array of `HH:MM` local), `days_of_week` (array 0–6), `interval_days`, `confirmation_window_minutes`, `repeat_reminder_minutes`, `maximum_repeat_reminders`, `escalation_enabled`, `first_escalation_delay_minutes`, `second_escalation_delay_minutes`, `active`, timestamps.
- [ ] `app/models/dose_instance.py` — `dose_instances`: `id`, `schedule_id`, `medication_id`, `patient_id`, `scheduled_at` (UTC), `status` (enum per spec: `UPCOMING…EXPIRED`), `confirmed_at`, `confirmation_method` (enum per spec), `user_note`, `idempotency_key` (nullable, unique), timestamps. **Unique `(schedule_id, scheduled_at)`** — the cornerstone of duplicate-free generation.
- [ ] `app/models/outbox.py` — `outbox_events`: `id`, `event_id` (uuid unique), `event_type`, `event_version`, `payload` (jsonb), `correlation_id`, `created_at`, `published_at` (null = pending), `attempts`. (Table now; publisher in Phase 3; hardening in Phase 4.)
- [ ] `app/models/audit.py` — `access_audit`: append-only log of reads/writes on medication/dose data (`actor_id`, `patient_id`, `action`, `resource`, `correlation_id`, `created_at`).
- [ ] Alembic migration `0001_initial_medication`.

### Tasks — dose generation engine (pure logic first)

- [ ] `app/services/dose_generation.py` — pure function `generate_occurrences(schedule, from_utc, to_utc) -> list[datetime]`: converts local `scheduled_times` in the schedule's IANA timezone to UTC per occurrence date; handles DAILY, WEEKLY (`days_of_week`), INTERVAL (`interval_days` anchored at `start_date`); respects medication `start_date`/`end_date` and `active`; correct across DST (nonexistent local times → shift forward; ambiguous → first occurrence; document in module docstring).
- [ ] `app/services/dose_materializer.py` — `materialize(schedule, horizon_days=3)`: upsert `dose_instances` (`ON CONFLICT (schedule_id, scheduled_at) DO NOTHING`) for a rolling horizon; called on schedule create/update and by a periodic job (Phase 3 Celery beat; for now a `make generate-doses` management command `app/cli.py`). Schedule modification: delete/regenerate only **future `UPCOMING`** instances, never confirmed history. Deactivating a medication/schedule expires future `UPCOMING` doses (`EXPIRED`).

### Tasks — medication-service API

- [ ] `app/api/medications.py` — `POST /medications`, `GET /medications`, `GET /medications/{id}`, `PATCH /medications/{id}`, `DELETE /medications/{id}` (soft: `active=false`). Patient-scoped: `patient_id` always taken from JWT, never the body (patient isolation).
- [ ] `app/api/schedules.py` — `POST /schedules`, `GET /schedules?medication_id=`, `PATCH /schedules/{id}`, `DELETE /schedules/{id}` (deactivate); create/update triggers materialization.
- [ ] `app/api/doses.py` — `GET /doses/today` (Today dashboard payload: next dose, time remaining, recent confirmations, upcoming), `GET /doses?from=&to=&status=` (history, paginated), `POST /doses/{id}/confirm` body `{status: TAKEN|SKIPPED|DELAYED, note?}` + required `Idempotency-Key` header (replay returns the original result, no state change); DELAYED sets a new effective reminder time (`scheduled_at + repeat_reminder_minutes`); writes `DoseConfirmed` to the outbox in the **same transaction** as the status update; late confirmations accepted and recorded as such (backend decides timely vs late by comparing `confirmed_at` to window).
- [ ] `app/api/caregiver_views.py` — caregiver read endpoints (`GET /patients/{patient_id}/doses`, `/medications`) that call `identity /internal/consents/check` for `VIEW_DOSE_HISTORY` / `VIEW_MEDICATION_NAMES`; 403 without active consent; every access audit-logged.
- [ ] `app/api/reports.py` — `GET /reports/adherence?from=&to=` (taken/skipped/missed counts, percentage) — minimal now, polished in Phase 5.

### Tasks — Angular skeleton (`frontend/angular-app/`)

- [ ] Scaffold Angular workspace (standalone components, Angular Material): `ng new angular-app`; base folders `src/app/{core,shared,features}`.
- [ ] `core/services/api.service.ts`, `core/services/auth.service.ts` (login/refresh/logout, token storage), `core/interceptors/jwt.interceptor.ts` (attach access token; on 401 attempt one refresh then logout), `core/interceptors/correlation-id.interceptor.ts` (uuid per request), `core/guards/auth.guard.ts`, `core/guards/role.guard.ts`.
- [ ] Feature pages (minimal, functional): `features/auth/{login,register}`, `features/today/today-dashboard.component.ts` (date, next medication, countdown, large **Taken / Remind me later / Skip** buttons, recent confirmations, upcoming doses), `features/medications/{list,form}`, `features/schedules/schedule-editor.component.ts`, `features/doses/dose-history.component.ts`.
- [ ] `app.routes.ts` with guarded routes; environment files pointing at `http://localhost:8000/api`.

### Tasks — tests (scheduling set)

- [ ] Unit (`services/medication-service/tests/test_dose_generation.py`): daily generation; multiple daily times; weekly on selected days; interval schedules; start/end date boundaries; **timezone conversion** (e.g., `Europe/Berlin` 08:00 local → correct UTC); **DST start** (02:30 nonexistent) and **DST end** (02:30 ambiguous); schedule modification regenerates only future doses; deactivated medication generates nothing and expires future doses.
- [ ] Integration: medication+schedule CRUD → dose instances materialized with correct UTC times; confirm endpoint is idempotent (same `Idempotency-Key` twice → one state change); patient A cannot read/confirm patient B's doses; caregiver without `VIEW_DOSE_HISTORY` gets 403, with it 200 and an audit row.

### Definition of done

- Patient registers, logs in, creates medication + schedule in the Angular UI, sees timezone-correct doses on the Today dashboard, and confirms them.
- All scheduling unit tests and isolation/consent integration tests pass in CI.

---

## Phase 3 — Reminders & Escalation (Events, Celery, Notification Service)

**Goal:** Event-driven pipeline end to end: due detection → outbox → RabbitMQ → idempotent notification consumer → initial/repeat reminders → overdue detection → first caregiver alert → acknowledgement → secondary escalation, with DLQs.

**Prerequisites:** Phase 2 (dose instances, outbox table, confirm endpoint), Phase 1 (escalation-contacts internal API).

### Tasks — messaging topology & infrastructure

- [ ] `infrastructure/rabbitmq/definitions.json` — topic exchange `adhera.events`; queues `notification.dose-events` (bindings `dose.*`) and `notification.alert-events` (`alert.*`); DLX `adhera.dlx` with `notification.dose-events.dlq` etc.; load via RabbitMQ container definitions mount in `docker-compose.yml`.
- [ ] Add to `docker-compose.yml`: `mailpit` (dev SMTP + web UI), `medication-worker` (Celery worker + beat, same image as medication-service, command `celery -A app.workers.celery_app worker -B`), `notification-worker` (worker for notification-service), `outbox-publisher` (or run as a thread/task inside medication-worker).

### Tasks — medication-service workers

- [ ] `app/workers/celery_app.py` — Celery app, broker = RabbitMQ (separate vhost or `celery` queue prefix so Celery traffic never mixes with domain events), result backend = Redis.
- [ ] `app/workers/tasks.py`:
  - `materialize_doses` (beat, every 15 min): rolling-horizon generation for all active schedules.
  - `mark_due_doses` (beat, every minute): `UPCOMING` doses with `scheduled_at <= now()` → `DUE`; each transition writes a **DoseDue** event to `outbox_events` in the same transaction. Wrap per-dose work in a Redis lock `lock:dose:{id}` (full lock infra hardened in Phase 4).
  - `mark_overdue_doses` (beat, every minute): `DUE` doses past `scheduled_at + confirmation_window_minutes` → `OVERDUE` + **DoseConfirmationOverdue** (with `overdue_minutes`) via outbox.
- [ ] `app/workers/outbox_publisher.py` — loop: `SELECT … FROM outbox_events WHERE published_at IS NULL ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED`; publish to `adhera.events` with routing key from `event_type` (`dose.due`, `dose.confirmed`, `dose.confirmation_overdue`), publisher confirms on; set `published_at`; increment `attempts` on failure. At-least-once by design — consumers dedupe.

### Tasks — notification-service data model

- [ ] `app/models/processed_event.py` — `processed_events`: `event_id` (pk), `event_type`, `processed_at`. Consumers insert here **in the same transaction** as their side-effect record; unique violation ⇒ duplicate ⇒ ack and skip.
- [ ] `app/models/notification.py` — `notifications`: `id`, `user_id`, `dose_instance_id`, `kind` (`INITIAL_REMINDER|REPEAT_REMINDER|CAREGIVER_ALERT|SYSTEM`), `channel` (`IN_APP|EMAIL|WEB_PUSH`), `status` (`PENDING|SENT|FAILED|CANCELLED`), `payload` jsonb, `sent_at`, `created_at`. `notification_preferences`: `user_id`, `channel`, `enabled`, `quiet_hours` **(stretch)**.
- [ ] `app/models/alert.py` — `alerts` per spec: `id`, `dose_instance_id`, `patient_id`, `caregiver_id`, `alert_level` (1|2), `status` (`PENDING|SENT|DELIVERED|ACKNOWLEDGED|FAILED|ESCALATED|CANCELLED`), `channel`, `sent_at`, `delivered_at`, `acknowledged_at`, `acknowledgement_note`, `retry_count`, timestamps; **unique `(dose_instance_id, alert_level)`** — duplicate overdue events cannot create duplicate alerts. `alert_delivery_attempts`: `id`, `alert_id`, `attempt_no`, `channel`, `status`, `error`, `attempted_at` (immutable audit). Alerts are append-only history (status transitions only, no deletes).
- [ ] Alembic migration `0001_initial_notification`.

### Tasks — notification-service consumer & workers

- [ ] `app/workers/celery_app.py` + `app/consumers/event_consumer.py` — aio-pika (or kombu) consumer on `notification.dose-events`/`notification.alert-events`: validate against JSON Schema, dedupe via `processed_events`, dispatch by `event_type`; on handler failure nack with requeue up to N (delivery-count header), then dead-letter. Manual ack only after DB commit.
- [ ] Handlers (`app/services/`):
  - `handle_dose_due` → create `notifications` row + send initial reminder (in-app row + email via Mailpit; web push in Phase 5); schedule `send_repeat_reminder` Celery task with countdown `repeat_reminder_minutes` (task re-checks DB state before sending — DB is the source of truth, the Celery eta is just a trigger).
  - `send_repeat_reminder(dose_instance_id, attempt_no)` — abort if dose already confirmed/escalated; stop after `maximum_repeat_reminders`.
  - `handle_dose_confirmed` → mark pending reminder `notifications` `CANCELLED`; if alerts exist for the dose, notify caregivers the dose was resolved **(stretch)**.
  - `handle_dose_overdue` → if `escalation_enabled`: fetch ordered escalation contacts from identity `GET /internal/patients/{id}/escalation-contacts` (only caregivers with **active `MISSED_DOSE_ALERTS` consent** — revoked caregivers are never alerted); create level-1 `alert` (`ON CONFLICT DO NOTHING`), send via channels, publish **CaregiverAlerted**; schedule `escalate_if_unacknowledged` with countdown `second_escalation_delay_minutes`.
  - `escalate_if_unacknowledged(alert_id)` → if alert still not `ACKNOWLEDGED`, mark `ESCALATED`, create level-2 alert for the secondary contact (if any), publish **CaregiverAlerted** (level 2).
- [ ] `app/services/channels/` — `in_app.py` (DB row), `email.py` (SMTP → Mailpit; templates without medication instructions in subject lines), `web_push.py` (Phase 5). Each attempt recorded in `alert_delivery_attempts`; per-attempt retry with exponential backoff (Celery `retry_backoff=True, max_retries=5`), then alert `FAILED` + DLQ entry.

### Tasks — notification-service API

- [ ] `app/api/alerts.py` — `GET /alerts` (caregiver: own active alerts; patient: alerts about them), `GET /alerts/{id}`, `POST /alerts/{id}/acknowledge` body `{note?}` + `Idempotency-Key` (first ack wins; concurrent/duplicate acks return the recorded ack — no error, no double effect); ack cancels the pending secondary escalation, sets `acknowledged_at`, publishes **AlertAcknowledged** via the notification-service's own `outbox_events` table (same pattern), and medication-service consumes it to set the dose `RESOLVED_BY_CAREGIVER`.
- [ ] `app/api/notifications.py` — `GET /notifications` (in-app inbox), `PATCH /notifications/{id}/read`, `GET/PUT /notification-preferences`.
- [ ] medication-service consumer — `app/consumers/alert_consumer.py`: consume `AlertAcknowledged` idempotently (medication-service also gains a `processed_events` table) → dose status `RESOLVED_BY_CAREGIVER`; consume `CaregiverAlerted` → dose status `CAREGIVER_ALERTED`.

### Tasks — Angular

- [ ] `features/alerts/{active-alerts,alert-detail,acknowledge-dialog}` (caregiver), `features/caregiver/dashboard`, in-app notification bell + list.

### Tasks — tests (reminder + escalation sets)

- [ ] Reminders: reminder sent exactly once per DoseDue; **duplicate DoseDue delivery → no duplicate reminder** (processed_events); repeat reminder fires after delay; confirmation cancels pending repeat reminders; late confirmation still recorded; Celery worker restart between schedule-and-fire loses nothing (state re-derived from DB by the sweeper — fully verified in Phase 4).
- [ ] Escalation: overdue → first caregiver alerted; caregiver with revoked consent **not** alerted; ack stops secondary escalation; no ack → secondary alerted after delay; **duplicate DoseConfirmationOverdue → single alert** (unique constraint); channel failure retries with backoff then DLQ + `FAILED` status; concurrent acknowledgements → exactly one recorded ack.
- [ ] Contract tests (`tests/contract/`): every published event validates against its `shared/event-schemas/*.v1.json`.

### Definition of done

- Unanswered dose → overdue → selected caregiver alerted in the caregiver UI → acknowledgement recorded and visible; secondary escalation works.
- Duplicate-event tests pass; DLQs visible in RabbitMQ management UI with poisoned messages.

---

## Phase 4 — Reliability Hardening

**Goal:** Make the pipeline provably survive crashes, restarts, duplicates, and DST — the portfolio's core engineering story.

**Prerequisites:** Phase 3 end-to-end flow working.

### Tasks

- [ ] **Distributed locks** — `shared/locks.py` (or per-service `app/locks.py`): Redis `SET NX PX` lock with token + Lua-checked release and TTL safety margin; wrap `mark_due_doses`/`mark_overdue_doses` per-dose processing and alert creation. Document fallback: PostgreSQL advisory locks (`pg_advisory_xact_lock(hashtext(dose_id))`) in `docs/adr/0004-distributed-locking.md`.
- [ ] **Outbox hardening** — publisher: publisher-confirms required before `published_at`; exponential backoff on broker outage; metric `outbox_pending_events`; alarm threshold documented. Add `outbox_events` retention cleanup task (delete published > 7 days).
- [ ] **Recovery sweeper** — `services/medication-service/app/workers/recovery.py` (beat, every 5 min): (a) `UPCOMING` doses whose `scheduled_at` passed but were never marked `DUE` → process now; (b) `OVERDUE` doses with `escalation_enabled` but no `DoseConfirmationOverdue` in outbox → emit; (c) unpublished outbox rows older than 2 min → re-attempt. `services/notification-service/app/workers/recovery.py`: (d) `PENDING`/`SENT` alerts past ack window with no scheduled escalation task → escalate; (e) `PENDING` notifications never sent → resend; (f) stale Celery eta tasks lost to worker death → re-derive from DB. Each recovery increments metric `recovery_actions_total{type=…}`.
- [ ] **Retry policy audit** — unify: consumer redelivery limit (x-delivery-count → DLQ), channel-send retries (backoff 1s→2s→4s→…, max 5), Celery task `acks_late=True` + `task_reject_on_worker_lost=True` so a killed worker's task is redelivered.
- [ ] **Business metrics** — Prometheus: RabbitMQ queue depth, `notifications_failed_total`, `notification_delivery_latency_seconds`, `alert_ack_latency_seconds`, `recovery_actions_total`, `outbox_pending_events`. Add Prometheus + Grafana to compose under `infrastructure/monitoring/` **(stretch: dashboards JSON)**.
- [ ] **Failure-simulation integration tests** (`tests/integration/test_reliability.py`, Testcontainers):
  - Duplicate message: publish same DoseDue twice → one reminder row.
  - Worker crash: SIGKILL notification worker mid-consume → message redelivered → still exactly one side effect.
  - Restart: stop/start medication-service + workers → no dose lost, sweeper picks up missed due doses.
  - Broker outage: stop RabbitMQ 60 s → outbox drains completely after recovery.
  - DST end-to-end: schedule at 02:30 local across the transition dates → correct UTC reminder times.
  - Redis lock contention: two concurrent `mark_due` runs → single DoseDue per dose.
- [ ] `docs/ARCHITECTURE.md` — finalize reliability section with the actual mechanisms + failure-mode table; `docs/adr/0002-transactional-outbox.md` filled in.

### Definition of done

- Duplicate events never produce duplicate alerts; restarts erase nothing (proven by the failure-simulation suite in CI).
- Reliability integration tests run against real Postgres/Redis/RabbitMQ containers in CI.

---

## Phase 5 — Frontend Polish, Offline, Web Push, E2E

**Goal:** Complete, accessible patient and caregiver UIs; offline confirmation queue; web push; adherence reports; Playwright e2e.

**Prerequisites:** Phases 1–4 (all backend flows stable).

### Tasks — backend additions

- [ ] Web push: generate VAPID keypair (env vars `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`); notification-service `app/models/push_subscription.py` (`push_subscriptions`: `user_id`, `endpoint` unique, `p256dh`, `auth`, `created_at`), `app/api/push.py` — `GET /push/vapid-public-key`, `POST /push/subscriptions`, `DELETE /push/subscriptions`; `channels/web_push.py` via `pywebpush` (410/404 → delete subscription).
- [ ] Offline sync support: `POST /doses/confirmations/batch` on medication-service — accepts queued confirmations `{dose_instance_id, status, client_confirmed_at, idempotency_key}[]`; backend classifies timely vs late from `client_confirmed_at` vs window; conflicts (dose already `RESOLVED_BY_CAREGIVER`/`EXPIRED`) recorded as conflict entries, **never overwritten** — returns per-item outcome.
- [ ] `GET /users/me/export` — JSON export of profile, medications, doses, alerts.
- [ ] Adherence report endpoint finalized: per-medication and overall percentages, streaks, date-range filters.

### Tasks — Angular (full app)

- [ ] **Patient pages**: Today dashboard (polished: large buttons, countdown), upcoming doses, medication list/create/edit, schedule editor (times, days, windows, escalation delays), dose confirmation flow, dose history (filters), caregiver management (invite, revoke, escalation order), consent management (per-scope toggles with plain-language descriptions), notification preferences, adherence report (charts), profile/timezone editor.
- [ ] **Caregiver pages**: dashboard, active alerts, alert detail, acknowledge (with note), patient list, shared dose history (consent-gated — hide what consent doesn't allow), notes (`ADD_NOTES` scope), notification preferences.
- [ ] **Offline queue** — `core/services/offline-queue.service.ts`: cache today's/upcoming doses in IndexedDB (`idb`); when offline, enqueue confirmations locally with client timestamp + generated idempotency key; on reconnect (`online` event + retry timer) flush to `/doses/confirmations/batch`; show per-item sync status and any conflicts. Angular service worker (`@angular/pwa`) for asset caching + push handling.
- [ ] **Web push** — `core/services/push.service.ts`: subscribe with VAPID public key, register subscription; service-worker notification click → deep link to dose/alert.
- [ ] **Accessibility pass** — icons + text labels everywhere, WCAG AA contrast, no color-only status (badge text + icon), confirm dialogs before destructive actions (revoke caregiver, delete medication), screen-reader labels (`aria-*`), full keyboard nav, adjustable text size setting, `prefers-reduced-motion` respected.
- [ ] Error/empty/loading states; global toast for API errors with correlation ID shown for support.

### Tasks — Playwright e2e (`tests/end-to-end/`)

- [ ] Setup: `playwright.config.ts`, seeded synthetic accounts via a `scripts/seed_demo.py` API-driven seeder.
- [ ] Scenarios: patient registers → creates medication + daily schedule → dose appears on Today; patient confirms Taken → history updated; patient delays → repeat reminder state visible; dose left unconfirmed (short test windows) → caregiver sees active alert → acknowledges with note → patient history shows resolution; consent revoked → caregiver dashboard loses patient data immediately; offline: confirm while network blocked (Playwright route abort) → reconnect → confirmation synced; login rate limit surfaces friendly error; keyboard-only Today-dashboard confirmation; axe-core accessibility scan on key pages **(stretch)**.

### Definition of done

- All spec-listed patient and caregiver pages exist and are accessible; offline confirmations sync with conflict recording; web push delivers reminders to a subscribed browser.
- Playwright suite green in CI (headless, against Compose stack); the full reminder→escalation→acknowledgement story demonstrable entirely through the UI.

---

## Phase 6 — AI Assistant (Human-Approved Only)

**Goal:** Add strictly-bounded AI conveniences. **Every AI output is a proposal requiring explicit user approval before anything is created or changed. The prohibited-actions list is enforced in code, not just prompts.**

**Prerequisites:** Phase 5 (stable UI to host approval flows).

### Tasks — backend (`services/medication-service/app/ai/` module; separate `ai-service` is **stretch**)

- [ ] `app/ai/client.py` — LLM client wrapper (provider-agnostic; keys via env); records `model_id`, `prompt_version`, latency for every call.
- [ ] `app/models/ai.py` — `ai_proposals`: `id`, `user_id`, `kind` (`SCHEDULE_EXTRACTION|LABEL_OCR|VOICE_REMINDER|SIMPLIFY_INSTRUCTIONS|WEEKLY_SUMMARY|CONFLICT_CHECK`), `input_ref` (hash/pointer — raw inputs not retained long-term), `output` jsonb, `model_id`, `prompt_version`, `status` (`PROPOSED|APPROVED|REJECTED|EXPIRED`), `decided_at`, `decided_by`, timestamps. `ai_audit_log`: append-only record of every AI call and decision.
- [ ] `app/ai/guardrails.py` — hard output validator run on every proposal: schema-validate structured outputs; **reject** anything containing dosage-change recommendations, stop/double-dose instructions, late-dose decisions, diagnoses, symptom interpretation (incl. hallucinations/delusions/psychosis prediction), emergency-contact actions, or clinician-style language; unit-tested denylist + structural checks. Missed-dose guidance endpoint returns **only the human-entered `instructions` field** — never generated text.
- [ ] `app/api/ai.py` — `POST /ai/schedule-extraction` (free text → proposed medication+schedule JSON), `POST /ai/label-ocr` (image upload → extracted fields proposal), `POST /ai/simplify-instructions` (existing instructions → simplified/translated text proposal), `GET /ai/proposals`, `POST /ai/proposals/{id}/approve` (server applies via the **normal, authorized CRUD paths** — no bypass), `POST /ai/proposals/{id}/reject`. `POST /ai/voice-reminder` **(stretch)**. `GET /ai/weekly-summary` (plain-language adherence summary from dose history; generated on demand, marked "AI-generated, not medical advice"). `POST /ai/conflict-check` (flags overlapping/duplicate schedule times — informational only).
- [ ] Rate-limit and role-gate all `/ai/**` at the gateway; AI endpoints disabled entirely when `AI_FEATURES_ENABLED=false` (default off).

### Tasks — Angular

- [ ] `features/ai/schedule-from-text.component.ts` (textarea → proposal), `features/ai/ocr-upload.component.ts`, `features/ai/approval-screen.component.ts` — side-by-side "what the AI proposes" vs editable form; explicit **Approve** / **Reject**; nothing saved until approve; visible "AI-generated — review before accepting" banner; weekly summary card on dashboard (clearly labeled, dismissible).

### Tasks — tests

- [ ] Unit: guardrail validator rejects each prohibited category (table-driven tests); proposals never auto-apply; approve path reuses standard authorization; missed-dose guidance returns only stored human instructions.
- [ ] Integration: proposal lifecycle (propose → approve → medication created with audit trail incl. `model_id` + `prompt_version`); reject leaves no side effects; AI disabled flag returns 404/403.

### Definition of done

- Every AI feature is proposal-then-approve; `ai_audit_log` captures model + prompt versions; guardrail tests cover the full prohibited list; app remains fully functional with AI disabled.

---

## Phase 7 — Deployment

**Goal:** One public, HTTPS-secured demo deployment with managed Postgres, secrets management, monitoring, backups documentation, and synthetic demo accounts.

**Prerequisites:** Phases 0–5 (Phase 6 optional in the deployed demo).

### Tasks

- [ ] Choose target (documented in `docs/adr/0005-deployment-target.md`): single VM + Docker Compose behind Caddy/Traefik (simplest for solo) or a PaaS (Fly.io/Render) — pick one.
- [ ] Production compose/manifests in `infrastructure/docker/docker-compose.prod.yml`: no exposed DB/broker ports, resource limits, restart policies, health-check-gated dependencies, non-root images, pinned digests.
- [ ] Managed PostgreSQL (one instance, per-service databases) — connection strings via secret store; TLS required; migration job step in deploy.
- [ ] HTTPS — Caddy/Traefik with automatic Let's Encrypt; HSTS; gateway is the only public service.
- [ ] Secrets — provider secret manager or encrypted env (SOPS/age); rotate JWT signing key procedure documented; verify gitleaks stays green.
- [ ] CI/CD — GitHub Actions deploy workflow: build → Trivy scan (fail on high/critical) → push images (GHCR) → deploy on tag; CodeQL/Semgrep job added to CI.
- [ ] Monitoring — uptime check on `/health`; Prometheus scrape + Grafana (or hosted equivalent); alert on `outbox_pending_events` and DLQ depth **(stretch: alerting rules)**.
- [ ] Backups — document (in `docs/OPERATIONS.md`): managed-Postgres automated backups, restore drill steps, event-schema/versioning compatibility notes.
- [ ] Demo data — `scripts/seed_demo.py` creates synthetic patient + caregiver accounts (clearly fake names/emails), sample medications/schedules; a demo banner in the UI stating prototype status ("not a medical device").
- [ ] Final docs pass — `README.md` quickstart + live demo link, `docs/API.md` per-service Swagger links, `docs/USER_GUIDE.md` walkthrough with screenshots, `docs/SECURITY.md` threat-model summary.

### Definition of done

- Public HTTPS demo reachable; demo accounts work end to end (register → schedule → remind → escalate → acknowledge) with synthetic data only.
- CI pipeline: lint, types, unit, Testcontainers integration, Playwright e2e, pip-audit, gitleaks, CodeQL/Semgrep, Trivy — all green.
- All acceptance criteria in PROJECT_SPEC.md verifiably met.

---

## Cross-Phase Test Traceability (spec "Essential Tests" → phases)

| Spec test group | Phase |
|---|---|
| Scheduling (daily/weekly/monthly, DST, modification, deactivation) | 2 |
| Reminders (once-only, duplicate events, repeat, cancel, late, worker restart) | 3 (restart proof in 4) |
| Escalation (first/secondary, revoked consent, consent-gated visibility, ack, duplicates, retry, DLQ) | 3 (failure sims in 4) |
| Security (isolation, consent, revocation immediacy, token expiry, rotation, rate limits, log masking) | 1 (extended in 2 and 5 e2e) |
