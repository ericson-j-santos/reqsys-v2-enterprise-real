# Native local-stack contract projection

## Purpose and scope

Remove Docker Compose execution from the production configuration assertions in
tests/test_local_docker_restart_guard.py. Read only the two versioned inputs,
docker-compose.yml and docker-compose.prod.yml, with an explicit synthetic
environment. This is a bounded contract projection, not a general Compose
parser, a captured Docker rendering, or proof that containers start or are
reachable.

## Requirements

1. Use a yaml.SafeLoader subclass. Reject duplicate/non-string mapping keys,
   unsupported tags, and unsupported fields within the contract. Permit
   !override only as a mapping at services.<name>.depends_on.
2. Interpolate each file before merging, including nested defaults, explicit
   required variables, and literal dollars escaped with $$. Never consult
   os.environ, .env, credential stores, external files, or subprocesses.
3. Normalize explicit environment KEY=value lists into mappings. Preserve map
   merge, whole depends_on replacement with !override, explicit profiles, the
   supported short port form, healthcheck test replacement, and build args.
4. Require exactly the six current services. The active production set is api,
   db, frontend, kb, nginx. Base restart is no; active production restart is
   on-failure:5. MailHog stays opt-in, restart no, and outside API dependencies.
5. Preserve production identity, demo login disabled, the seven nonempty
   required values, optional SMTP relay isolation, private API/database ports,
   the production frontend build/healthcheck, and the gateway publication and
   health/dependency assertions.
6. Reject constructs that would change interpretation without support,
   including include, extends, env_file, deploy.restart_policy, unknown service
   fields, unsupported dependency options, port forms, and misplaced tags.
   The known logging/volumes/networks/image/expose/command fields are traversed
   for safe YAML/interpolation only, then omitted from the projection. Their
   runtime behavior, images, mounts, commands and network reachability are not
   validated or claimed.
7. Preserve both original positive tests, all seven missing-required-value
   cases, and all other existing tests. Keep real preflight negatives with the
   Docker sentinel unchanged. Add native mutation controls in the same file
   already explicitly selected by Fast CI. Do not alter workflows or gates.
8. Errors expose diagnostic codes and variable names, never substituted values
   or YAML parser excerpts. Suppress the original YAML exception cause.

## Acceptance criteria and evidence limits

The existing pytest target must pass in CI without a Docker configuration
subprocess. Added controls cover interpolation, explicit inputs, omitted
required variables, per-file evaluation, healthcheck replacement, profile
activation, and 20 invariant/unsupported-form mutations. No captured Compose
output fixture was located in the inspected versioned tree; tests use explicit
expected projections, not a claimed differential comparison.

Preparation consisted of static review only. No Python, pytest, shell, Docker,
host operation, CI dispatch, or runtime verification was executed while
preparing these files. Existing platform-dependent skips remain unchanged.
Production deployment, container/runtime acceptance, credentials, networking,
workflow gates and scoring remain outside this change.

## References

- https://docs.docker.com/reference/compose-file/interpolation/
- https://docs.docker.com/reference/compose-file/merge/
- https://docs.docker.com/reference/compose-file/services/#depends_on
- https://docs.docker.com/reference/compose-file/profiles/

## Existing authorization traceability

This four-file delta removes Docker CLI only from the validation required by
the same native CI effort. It introduces no workflow, gate, or runtime and
opens no new workstream. The existing gate has no file allowlist, but prohibits
new workstreams. These records do not claim new test results or merge approval.

- Gate run: 39962211237
- Reference: OPS-GAP-TEAMS-NATIVE-CI-BOOTSTRAP
- Artifact: 12505321847
- Artifact digest: bda7319a84af293b6ed6d3e6e93edb5c855ae4498506fba5b61a3164e4cdfb39
- Prior validated SHA: 2b5fa2a8ab628b9b8b661823b1b863385ff21759
- Publication remains pending explicit release; this update is local only.
