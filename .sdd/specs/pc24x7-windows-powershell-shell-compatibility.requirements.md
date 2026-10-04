# PC24x7 — compatibilidade de shell dos workflows Windows

## Objetivo

Eliminar a dependência implícita de PowerShell 7 (`pwsh`) nos workflows executados pelo runner governado `DESKTOP-PDQK954`, cujo contrato de bootstrap não provisiona PowerShell 7.

## Contexto evidenciado

- Issue: #1927.
- Runner GitHub Actions: `DESKTOP-PDQK954`, versão `2.337.0`.
- SHA base: `51b0c283d72355bf5f54ba499927af29102c7678`.
- Run de pickup real: `35673844428`.
- Falha observada: `pwsh: command not found`.
- O Windows PowerShell disponível deve ser invocado explicitamente como `shell: powershell`.

## Requisitos

1. Workflows com `runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]` não podem depender de `shell: pwsh` enquanto PowerShell 7 não fizer parte do contrato de bootstrap do host.
2. Os comandos atuais compatíveis com Windows PowerShell 5.1 devem usar `shell: powershell`.
3. A mudança não pode alterar repositório, host, labels, permissões, segredos, ambiente ou semântica funcional dos workflows.
4. Um teste de regressão deve varrer os workflows PC24x7 e falhar se `shell: pwsh` reaparecer.
5. O Pre-PR Readiness deve validar o HEAD exato e permanecer `behind_by=0`.
6. A aceitação runtime exige novo pickup do runner PC24x7 e execução além da etapa de resolução do shell no mesmo SHA da mudança.
7. Nenhum deploy, produção, reboot, instalação de software ou leitura de segredo é autorizado por esta mudança.

## Workflows cobertos

- `.github/workflows/desktop-rdc-recovery.yml`
- `.github/workflows/codex-ollama-e2e-dev.yml`
- `.github/workflows/figma-github-e2e-dev.yml`
- `.github/workflows/ollama-ci-triage.yml`
- `.github/workflows/codex-worker-pool-handoff.yml`
- `.github/workflows/codex-worker-pool-smoke-dev.yml`

## Critérios de aceite

- Zero ocorrência de `shell: pwsh` nos workflows PC24x7 cobertos.
- Todos os shells PowerShell explícitos desses workflows usam `shell: powershell`.
- `tests/test_pc24x7_workflow_shell_compatibility.py` aprovado.
- Testes direcionados selecionados pelo Pre-PR Readiness aprovados.
- `READY_FOR_PR=passed` no HEAD exato.
- E2E PC24x7 comprova que a execução ultrapassa a falha anterior `pwsh: command not found`.
