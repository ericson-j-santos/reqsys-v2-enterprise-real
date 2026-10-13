# Windows Linux capability diagnostic

## Objective
Provide a bounded, read-only diagnostic for Windows virtualization metadata and registered WSL count without launching WSL, Linux, systemd, services, or installers.

## Requirements
1. Require exact host identity and a full 40-character source SHA.
2. Read processor capability flags through the Windows API only.
3. Read only the count of registered WSL distributions; never collect distribution names or personal paths.
4. Never invoke subprocesses, shells, WSL, systemd, service control, boot configuration, Docker, or network access.
5. Emit sanitized JSON to stdout only and never write evidence files.
6. Report systemd as unknown and Linux readiness as false until a separately authorized physical proof exists.
7. Tests must fully mock host APIs and run on GitHub-hosted CI without touching physical runners.

## Acceptance criteria
- Exact host and source SHA mismatches fail closed.
- Output contains only sanitized capability metadata and a distribution count.
- WSL, Linux, systemd, services, Docker, network and installers are never invoked.
- Physical readiness remains false without separately authorized runtime evidence.
