# Windows Linux capability diagnostic

## Objective
Provide a bounded, read-only diagnostic for Windows virtualization metadata and the current executor user's registered WSL distribution count without launching WSL, Linux, systemd, services, or installers.

## Requirements
1. Require exact host identity and a full 40-character requested source SHA.
2. Treat the requested SHA as unverified input; emit no observed SHA and never claim source provenance without a separately authorized integrity mechanism.
3. Read processor capability flags and optional Windows version through native Python Windows APIs only; never use `platform` fallbacks that may invoke a shell.
4. Read only the count of WSL distributions registered in the current executor user's HKCU; never collect distribution names or personal paths and never describe the result as host-wide.
5. Only a valid registry query or an absent registry key may produce a measured zero count. Access denial, unavailable APIs, query failures and invalid data must be unknown or unavailable with a fixed reason and null count.
6. Never invoke subprocesses, shells, WSL, systemd, service control, boot configuration, Docker, or network access.
7. Emit sanitized JSON to stdout only and never write evidence files or external exception text.
8. Report systemd as unknown and Linux readiness as false until separately authorized physical proof exists.
9. Tests must fully mock host APIs and run on GitHub-hosted CI without touching physical runners.

## Acceptance criteria
- Exact host and requested SHA format errors fail closed.
- A syntactically valid requested SHA remains explicitly unverified.
- Output contains only sanitized capability metadata and a current-executor HKCU distribution count.
- A valid zero-subkey query and an absent key may produce zero; every registry failure remains distinguishable and cannot leak exception text.
- WSL, Linux, systemd, services, Docker, network and installers are never invoked.
- Physical readiness remains false without separately authorized runtime and source-provenance evidence.
