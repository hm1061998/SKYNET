# ADR-003: Policy enforced in code

- Status: Accepted
- Date: 2026-07-22

## Context

Current approval is a dashboard convention. Skills and recovery can access the host, open applications, run subprocesses and install packages. Prompt instructions cannot reliably enforce permission or approval boundaries.

## Decision

Use a deny-by-default policy service over typed actors, actions, resources, risks, scopes and budgets. Dispatch requires a code-generated allow decision or a matching persisted human approval. Approvals bind identity, action, scope, Work Order/task, plan/artifact version and expiry. Separation of duties is validated in domain code.

## Consequences

LLMs can classify risk or recommend permissions but cannot authorize. All execution paths, including legacy adapters used by the new runtime, must pass through the policy boundary. Some existing autonomous behavior will later require dry-run or approval, introduced only with compatibility flags and tests.
