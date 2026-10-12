# PC24x7 DEV recovery safety

## Acceptance Criteria

- The tool refuses hosts, environments, Compose projects, services, roots, paths, and container cardinalities outside the fixed DEV scope.
- Capture and validation record only sanitized metadata and never read or emit runtime credentials, environment values, container logs, or database contents.
- Image preservation uses deterministic rollback tags and verifies each tag independently before any later deployment can be authorized.
- Rollback requires the exact confirmation phrase, an intact manifest fingerprint, preserved images, and the original ordered Compose inputs.
- The read-only deployment check requires the expected runtime SHA, healthy endpoints, one API container, and a sanitized successful `SELECT 1` result.
- Tests cover negative guards, collision and tamper failures, bounded readiness, liveness contracts, rollback sequencing, and direct script invocation.
- No operation in this increment deploys to DEV or touches TEST, HML, STG, PROD, secrets, networking, or branch protection.
