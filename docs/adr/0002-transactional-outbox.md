# ADR 0002 — Transactional outbox for domain events

## Status
Proposed (stub — to be filled in during Phase 4 hardening)

## Context
Dose state changes (DUE, OVERDUE, confirmed) must reach the notification
service reliably. Publishing to RabbitMQ inside a database transaction is
impossible; publishing after commit can be lost on a crash, and publishing
before commit can announce state that was rolled back.

## Decision
Write events to an `outbox_events` table in the **same transaction** as the
state change. A background publisher polls unpublished rows
(`FOR UPDATE SKIP LOCKED`), publishes to the `adhera.events` exchange with
publisher confirms, then marks `published_at`. Delivery is at-least-once;
consumers deduplicate via a `processed_events` table.

## Consequences
- No lost or phantom events across crashes and broker outages.
- Consumers must be idempotent (dedupe on `event_id`).
- Adds a polling component and an outbox retention/cleanup task (Phase 4).
- Open items for Phase 4: publisher backoff policy, `outbox_pending_events`
  metric and alarm threshold, retention window.
