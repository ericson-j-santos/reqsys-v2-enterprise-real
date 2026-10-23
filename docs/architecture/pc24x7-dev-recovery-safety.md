# PC24x7 DEV recovery safety design

## Scope

This design applies only to `DESKTOP-PDQK954`, environment `dev`, Compose project
`wt-pc24x7-piloto`, and the Compose-observed governed runtime root
`C:\dev\chatgpt-workers\wt-pc24x7-public-dev-governed`. It does not
authorize production operations, deployment, secret reads, or network changes.

## State machine

1. `capture`: reads container/Compose metadata, ordered config and env-file paths,
   immutable image IDs, runtime identity, and file hashes. It emits a sealed
   manifest and its external fingerprint.
2. `prepare`: requires the preserved capture fingerprint and an explicit
   confirmation. It creates deterministic rollback tags, verifies every tag by
   readback, and writes a durable secret-free Compose override under
   `.reqsys-recovery`.
3. `rollback`: requires the prepared manifest fingerprint and a separate explicit
   confirmation. It revalidates host, root, service cardinality, Compose labels,
   images, tags, files, identity, and readiness before mutation and between phases.

For the explicitly approved public DEV cutover wrapper, an unavailable candidate
API is an allowed rollback trigger, not a reason to strand the deployment. In that
case the pre-mutation guard still revalidates host, canonical root, Compose project,
service cardinality, labels and image IDs without claiming candidate readiness.
All post-rollback identity, readiness and database checks remain mandatory.

The fingerprint supplied by the operator is evidence external to the manifest.
Recalculating a fingerprint inside a modified manifest cannot satisfy the gate.
Prepared recovery state includes immutable private snapshots of each service's
ordered Compose manifests and fixes Compose `--project-directory` to the canonical
runtime root. A partial, previously governed recreation can legitimately leave the
API with a different ordered source chain from frontend and nginx; schema 3 seals
those chains separately instead of flattening them. Rollback groups services only
when their sources are identical and otherwise replays each exact chain. Environment
files stay in their original location and are never duplicated. This keeps rollback
valid after a tracked-source fast-forward without copying secrets.

## Rollback phases

- Restore API and frontend from deterministic tags without building.
- Poll identity and readiness with a monotonic bounded deadline.
- Execute a fixed, sanitized `SELECT 1` through stdin using `app.db.SessionLocal`,
  which is compatible with the preserved runtime SHA.
- Revalidate the manifest and physical DEV identity.
- Restore nginx and poll identity/readiness again.
- Verify all running image IDs equal the captured immutable IDs.

## Read-only deploy check

`deploy-check --expected-sha <full-sha>` is independent of rollback evidence. It
uses the same physical DEV guards, bounded readiness polling, unique API-container
resolution, and fixed stdin database probe. It never invokes Compose, tags an image,
restarts a service, writes a manifest, or reports success before the exact SHA,
health/readiness/liveness, and `SELECT 1` all pass.

The liveness contract supports the two implementations present in both the
preserved and current source: `{alive: true}` from the operational router, or
`{status: "alive"}` from the direct application route. HTTP success alone is not
enough; false, missing, or contradictory liveness fields are rejected.
When both fields are present, each is validated independently: `alive` must be the
exact boolean `true`, and `status` must be an accepted string. Invalid `alive` types
are retained only as a sanitized invalid-type marker so normalization cannot hide a
contradiction or leak its value.
The same rule applies to `status`: a present non-string becomes only
`status_invalid_type: true`. Health, readiness, and liveness reject that marker
before interpreting any companion field.

No phase retries indefinitely. Expected transport/HTTP/JSON probe failures become
sanitized transient readiness failures; unexpected programming errors remain
terminal.

## Path and secret controls

Paths are checked lexically for traversal and reparse points before canonical
resolution. Compose config and env-file order must be present and internally stable
for each service; cross-service differences are preserved, never reordered or
merged. Env-file values are never read for execution or emitted; only file metadata
is sealed. The durable override contains image tags only and must remain present
while containers can reference it through Compose labels.

## Non-goals

- Automatic deployment or rollback.
- Production, staging, or a different host/project.
- Image pruning, secret rotation, container log collection, or database export.

The last item applies to this standalone image-recovery command. The separate
`pc24x7_public_dev_cutover_guard.py` wrapper is allowed to create a DEV-only
PostgreSQL backup because it keeps only DPAPI ciphertext, proves an isolated
networkless restore and never uploads the dump or its private manifest.
