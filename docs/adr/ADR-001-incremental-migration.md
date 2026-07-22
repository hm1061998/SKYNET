# ADR-001: Incremental migration

- Status: Accepted
- Date: 2026-07-22

## Context

The repository has working CLI, dashboard, provider, skill, generation, recovery, memory and mock paths concentrated around `SkillAgent`. A rewrite would discard undocumented contracts and make regression diagnosis difficult.

## Decision

Build the governed runtime additively behind application ports and a `LegacySkillAgentAdapter`. Preserve current public APIs and storage until explicit parity, migration and rollback gates pass. Use request-level feature flags during cutover. Do not remove legacy modules as part of feature implementation.

## Consequences

Migration temporarily carries two paths and adapter code. This cost buys small reviewable phases, direct compatibility tests, reversible rollout and evidence-based removal. New domain rules must never be added to the compatibility adapter.
