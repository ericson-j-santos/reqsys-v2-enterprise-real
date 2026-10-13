# Fail-closed SQL capture mode preflight

## Objective

Make the DEV SQL capture workflow resolve an explicitly configured validation mode before any Azure OIDC, Key Vault, or direct SQL action, while preserving sanitized evidence for every blocked state.

## Requirements

1. The validation mode must be explicit. Empty and unsupported values fail closed.
2. Minimal `source.json` creation occurs immediately after checkout, before setup, dependency installation, tests, mode resolution, or Azure login.
3. `power_platform_gateway` never invokes Azure login, Key Vault secret retrieval, or the direct SQL locator.
4. Gateway evidence records direct connectivity and procedure validation as deferred to the real flow; it never claims SQL validation.
5. `direct_dsn` may proceed only after its configuration preflight is complete.
6. Missing configuration is recorded using fixed logical names and booleans only, without values.
7. The workflow must not reuse the retired Fly binding or the RBAC mutator identity as the reader.
8. Until a provider-neutral reader binding is independently confirmed, direct DSN remains blocked with `AZURE_CLIENT_ID_READER_BINDING=false`.
9. `oidc_login_failed` is emitted only after an actual login attempt fails.
10. Key Vault and SQL steps remain unreachable unless their preceding conditions succeed.
11. Setup, dependency, and contract-test outcomes are captured using fixed states; any failure or skipped prerequisite blocks every route.
12. Consolidation, artifact publication, and the final functional gate run even after an upstream block.
13. The exact DEV vault target must match `EXPECTED_KEY_VAULT_NAME` before login.
14. OIDC failure is recorded only for an actual `failure`; skipped or cancelled login is recorded as not attempted.
15. A previous failure can never be converted into a green result by a skipped downstream step.

## Acceptance criteria

- Behavioral tests cover setup/dependency/test failure before mode resolution and prove sanitized evidence remains available.
- Negative tests cover empty and invalid modes.
- Gateway tests prove Azure, Key Vault, and SQL steps are direct-mode guarded.
- Direct-mode tests cover missing reader binding and missing or invalid DSN reference.
- Tests distinguish configuration failure, login not attempted, and attempted-login failure.
- Tests reject a divergent Key Vault target without recording either vault name.
- Sanitized evidence preserves its original source category.
- The final gate remains fail-closed for every unresolved direct-mode state.
- No Fly credential binding, environment mutation, RBAC change, SQL execution, or E2E dispatch is introduced.
