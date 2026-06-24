# Workflow Stability Execution Plan

Date: 2026-06-24
Status: implemented in clean replacement branch
Supersedes: PR #120

## Context

PR #120 became non-mergeable due to branch divergence and merge conflicts after `main` advanced. The original scope remains operationally relevant, but applying it directly through the GitHub Web UI is no longer the safest path.

## Applied diagnosis

- `pr-ci-watch.yml` already contained part of the earlier stabilization on `main`.
- The remaining high-impact gap was concurrency behavior for repeated PR CI Watch executions.
- `pr-scope-labeler.yml` remained read-only and safe, but lacked explicit job-level fail-safe controls and concurrency cancellation.
- The replacement branch was created directly from the current `main` to avoid carrying stale conflict state from PR #120.

## Implemented decision

- Preserve the current `main` behavior for PR CI Watch context resolution and artifact generation.
- Change PR CI Watch concurrency to use the workflow run head SHA instead of workflow run id where applicable.
- Enable cancellation of duplicate in-progress PR CI Watch executions.
- Add explicit concurrency and fail-safe job behavior to PR Scope Labeler.
- Keep the change limited to workflow stability P0 and documentation.

## Acceptance criteria

- The replacement PR is created from the current `main`.
- PR CI Watch no longer accumulates duplicate active executions for the same PR/head SHA.
- PR Scope Labeler does not block the PR flow if labeling/classification fails.
- The change does not alter deploy, secrets, production environments or runtime application code.
