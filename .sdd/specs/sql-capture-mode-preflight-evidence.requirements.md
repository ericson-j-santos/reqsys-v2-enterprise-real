# Fail-closed SQL capture mode preflight

## Objective

Make the DEV SQL capture workflow resolve an explicitly configured validation mode before any Azure OIDC, Key Vault, or direct SQL action, while preserving sanitized evidence for every blocked state.

## Requirements

1. The validation mode must be explicit. Empty and unsupported values fail closed.
2. Mode resolution and initial `source.json` creation occur before any Azure login.
3. `power_platform_gateway` never invokes Azure login, Key Vault secret retrieval, or the direct SQL locator.
4. Gateway evidence records direct connectivity and procedure validation as deferred to the real flow; it never claims SQL validation.
5. `direct_dsn` may proceed only after its configuration preflight is complete.
6. Missing configuration is recorded using fixed logical names and booleans only, without values.
7. The workflow must not reuse the retired Fly binding or the RBAC mutator identity as the reader.
8. Until a provider-neutral reader binding is independently confirmed, direct DSN remains blocked with `AZURE_CLIENT_ID_READER_BINDING=false`.
9. `oidc_login_failed` is emitted only after an actual login attempt fails.
10. Key Vault and SQL steps remain unreachable unless their preceding conditions succeed.
11. Consolidation, artifact publication, and the final functional gate run even after an upstream block.
12. A previous failure can never be converted into a green result by a skipped downstream step.

## Acceptance criteria

- Negative tests cover empty and invalid modes.
- Gateway tests prove Azure, Key Vault, and SQL steps are direct-mode guarded.
- Direct-mode tests cover missing reader binding and missing or invalid DSN reference.
- Tests distinguish configuration failure from attempted-login failure.
- Sanitized evidence preserves its original source category.
- The final gate remains fail-closed for every unresolved direct-mode state.
- No Fly credential binding, environment mutation, RBAC change, SQL execution, or E2E dispatch is introduced.
