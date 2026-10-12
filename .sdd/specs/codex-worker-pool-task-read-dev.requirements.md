# Worker Pool task #2546 — diagnostic only

Incident ReqSys #1532, implementation issue #2546; authorized gateway issue #1705.

1. Only the owner exact command on issue #1705: /reqsys run codex-worker-pool-task-2546-read-dev.
2. Dispatch existing DEV workflow on main, fixed mode task-read, without arbitrary target, URL, or task-id parameters.
3. Require pinned rules SHA, Session Launcher, validated state, Command Gateway, immutable SHA, and actual Windows DESKTOP-PDQK954 runner.
4. Call exactly one read-only Worker Pool API path GET /v1/tasks/cwp-cdb85c31e3cc4e972f3094ab with local protected service token.
5. Validate repository, issue, request ID and original task base SHA. Sanitize worker identities and blocked reason.
6. Do NOT call /v1/snapshot, /v1/workers or /v1/repositories because snapshot may invoke lease recovery.
7. No new task, claim, requeue, Docker mutation, secrets disclosure, reboot, deploy, or Teams E2E.
8. Missing task or wrong identity, SHA, host, state, or HTTP status must fail closed and publish only sanitized evidence.
9. Worker eligibility and why_idle remain unverified; proving them requires another truly read-only contract.
10. Before a PR, require READY_FOR_PR=passed for the final branch SHA; merge only after required checks.
