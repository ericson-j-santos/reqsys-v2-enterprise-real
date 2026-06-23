# Workflow Stability Execution Plan

Date: 2026-06-22
Status: implemented in governed branch

## Context

The executive operational report from 2026-06-22 classified ReqSys as ATTENTION OPERATIONAL due to recurring auxiliary workflow instability and CI pipeline risk.

## Applied diagnosis

- pr-ci-watch was triggered by workflow_run without a workflow allowlist.
- workflow_run context could resolve pr_number as 0.
- PR Scope Labeler had no explicit fail-safe at job level.

## Implemented decision

- Restrict pr-ci-watch workflow_run to known CI workflows.
- Ignore workflow_run events without pull request context.
- Enable concurrency cancellation for repeated executions.
- Add fail-safe behavior to PR Scope Labeler.
- Keep the change small, reversible and auditable.

## Acceptance criteria

- PR CI Watch does not execute the Python monitor for pr_number 0.
- PR CI Watch observes only explicitly listed workflows.
- PR Scope Labeler does not block the PR flow if labeling fails.
- The change remains limited to workflow stability P0.
