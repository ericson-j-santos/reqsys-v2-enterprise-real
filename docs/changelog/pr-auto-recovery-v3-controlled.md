# Changelog — PR Auto Recovery Controlled v3

## Implemented

- Added ADR for controlled draft PR recovery.
- Added versioned gate configuration.
- Added operational runbook.
- Added controlled draft PR plan example.
- Added validation evidence.

## Safety

- Default execution is disabled.
- No automatic merge.
- No automatic close of original PR.
- No deploy.
- No secret mutation.
- No branch protection mutation.

## Next increment

Enable a guarded workflow_dispatch dry execution against a single PR number, still requiring human-controlled execution and review.
