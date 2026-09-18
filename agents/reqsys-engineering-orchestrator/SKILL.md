# ReqSys Engineering Orchestrator

Version: 1.0.0

## Purpose

Provide the canonical engineering-routing contract for ReqSys. This skill does not replace the existing Operational Orchestrator. It routes engineering requests to specialized roles and binds them to the existing Action Queue, Decision Gate, Evidence Ledger, governed executors, and human gates.

## Trigger

Use for ReqSys work involving implementation, CI/CD diagnosis or remediation, E2E validation, architecture/planning, pull requests, distributed workers, or requests for critical repository/runtime actions.

## Mandatory context

Before execution, resolve when applicable:
- repository, base branch, work branch, HEAD/SHA, working-tree/concurrency state;
- PR/issue/workflow/run/check state;
- environment and runtime target;
- applicable operational/project rules;
- correlation_id and evidence requirements.

## Routing

Routing is defined in `router.yaml`. Guardrails are defined in `guardrails.yaml`.

Canonical roles:
- `planner`: architecture, decomposition, requirements, next executable increment;
- `builder`: implementation in an isolated branch/worktree;
- `ci_remediator`: diagnose and minimally remediate CI failures;
- `e2e_validator`: independent end-to-end validation and false-positive controls;
- `human_gate`: critical actions that require explicit human authorization.

Builder and Validator should be separate whenever the available execution environment permits it.

## Execution protocol

1. Read current canonical rules and project rules.
2. Resolve current source state; never use remembered state as proof.
3. Classify route and risk.
4. Generate or preserve `correlation_id`.
5. Execute only within current authorization and tool policy.
6. Validate positive behavior and applicable negative/control behavior.
7. For idempotent operations, repeat the same input and prove no duplicate effect.
8. Bind evidence to the exact branch/SHA/environment.
9. If SHA changes, invalidate affected evidence and revalidate.
10. Report evidenced state, blockers, residual risks, and next safe action.

## Critical actions

Merge, production deployment/change, destructive database operations, permanent deletion, force-push, protected-branch mutation, administrative permission changes, secrets handling, and irreversible/high-impact actions route to `human_gate`.

The skill may prepare and validate a critical action, but must not execute it without explicit compatible authorization.

## Fail-closed rules

- Missing current state or required evidence prevents a green result.
- Missing required human authorization prevents a critical mutation.
- Tool failure must not be bypassed with an unrestricted terminal.
- Old workflow runs, old SHAs, logs alone, HTTP 2xx alone, or unit tests alone do not prove E2E completion.
- Never invent links, commits, runs, percentages, or evidence.

## Output contract

Use:
- 🟢 concluded/evidenced;
- 🟡 partial;
- 🔴 blocked;
- ⏳ pending.

Include, when applicable: current evidenced state, target, actions performed, validation, evidence, risks, blockers, pending items, and next safe action.
