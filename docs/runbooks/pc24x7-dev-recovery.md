# Runbook: governed PC24x7 DEV recovery

## Preconditions

- Use the repository session launcher and Command Gateway.
- Confirm the physical host is `DESKTOP-PDQK954` and the target is DEV only.
- Confirm all three Compose services report working directory
  `C:\dev\chatgpt-workers\wt-pc24x7-public-dev-governed`.
- Preserve the fingerprint printed by each successful evidence-producing phase
  outside the JSON manifest.
- Obtain review and explicit approval before `prepare` or `rollback`; both mutate
  Docker state. `capture` is read-only except for writing its local evidence file.

## Commands

Read-only post-deploy readiness and database check (no manifest or rollback required):

```text
python -B scripts/dev_runtime_recovery.py deploy-check \
  --expected-sha <deployed-full-sha>
```

This command performs no Compose write, restart, tag, or evidence-file write. It
waits for the exact SHA plus healthy runtime endpoints, resolves exactly one DEV API
container, and runs the fixed sanitized `SELECT 1` probe by stdin. It fails on host,
project, root, label or cardinality mismatch; readiness deadline; SHA mismatch;
database timeout/query failure; or malformed probe JSON.

Liveness must return HTTP 200 with either `alive: true` or `status: "alive"`, as
defined by the two existing route implementations. Redirects, timeouts, HTTP
errors, malformed JSON, `alive: false`, missing fields, or contradictory status are
terminal/transient failures handled within the bounded readiness deadline.
If both `alive` and `status` are returned, both must be valid; one valid field never
masks a false, mistyped, null, missing, or contradictory companion field.
Non-string `status` and non-boolean `alive` values are represented only by sanitized
invalid-type markers and always fail the gate; their original values are never
included in diagnostic output.

Capture current rollback evidence:

```text
python -B scripts/dev_runtime_recovery.py capture --manifest <approved-evidence-path>
```

After independent review, preserve images and create the durable override:

```text
python -B scripts/dev_runtime_recovery.py prepare \
  --manifest <approved-evidence-path> \
  --expected-fingerprint <capture-fingerprint> \
  --confirm PREPARE-ROLLBACK-PC24X7-PUBLIC-DEV
```

Validate prepared evidence without changing Docker:

```text
python -B scripts/dev_runtime_recovery.py validate \
  --manifest <approved-evidence-path> \
  --expected-fingerprint <prepared-fingerprint>
```

Execute rollback only after a failed or partial approved DEV deployment:

```text
python -B scripts/dev_runtime_recovery.py rollback \
  --manifest <approved-evidence-path> \
  --expected-fingerprint <prepared-fingerprint> \
  --confirm ROLLBACK-PC24X7-PUBLIC-DEV
```

## Stop conditions

Stop without improvising if host/root/project identity differs, service cardinality
is ambiguous, ordered Compose metadata differs between services, a reparse point is
found, a deterministic tag points to another image, evidence fingerprint differs,
readiness reaches its deadline, or the sanitized database probe fails.

Do not delete `.reqsys-recovery` while containers reference its override. Do not
retag, rebuild, recreate, or prune images outside the reviewed command sequence.

## Evidence

Record only command exit status, external fingerprint, sanitized phase category,
observed runtime SHA, and test results. Never attach env-file contents, raw driver
errors, connection strings, credentials, container logs, or database contents.
