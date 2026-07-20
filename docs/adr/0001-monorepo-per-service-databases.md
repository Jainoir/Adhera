# ADR 0001 — Monorepo with per-service databases

## Status
Accepted

## Context
Adhera consists of an API gateway and three backend services that must evolve independently but be easy to develop and demo as a portfolio project.

## Decision
Use a single monorepo. Each service runs in its own container and owns its own PostgreSQL database; services never read another service's tables. Synchronous calls use REST; asynchronous workflows use RabbitMQ events with versioned schemas.

## Consequences
Simple local development (one Docker Compose command), clear service boundaries, realistic microservices patterns (outbox, idempotent consumers) without multi-repo overhead.
