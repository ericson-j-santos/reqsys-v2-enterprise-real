# Desktop Admin Broker Local Kick

## Objetivo

Permitir que o runner governado do próprio `DESKTOP-PDQK954` solicite somente o start local da tarefa já existente `\Automation\ReqSysDesktopAdminBroker`, sem GUI, RPC remoto ou credenciais.

## Requisitos

1. Origem e destino fixos `DESKTOP-PDQK954`.
2. Runner fixo `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
3. Tarefa fixa `\Automation\ReqSysDesktopAdminBroker`.
4. Única mutação permitida: `schtasks.exe /Run /TN <task>` local; `/S` é proibido.
5. Proibidos `/Create`, `/Change`, `/Delete`, `/U`, `/P` e argumentos externos.
6. Nenhum segredo, reboot, deploy ou produção.
7. Evidência sanitizada como artifact.
8. Execução somente por workflow self-hosted do Desktop e comando exato no Authorized Actions Gateway.
9. A operação local é acionada somente por `workflow_dispatch`; `pull_request`, `pull_request_target` e `push` validam apenas contratos, sem executar a tarefa.
10. O workflow usa CPython 3.12.10 embeddable oficial, validado por SHA-256 com a API .NET, sem depender do PATH do host.

## Critérios de aceite

- sucesso registra `EXISTING_DESKTOP_ADMIN_BROKER_RUN_REQUESTED`;
- tarefa ausente ou falha local termina fail-closed;
- `task_created_or_modified=false`;
- `credentials_supplied=false`;
- testes validam argv exato e ausência de credenciais.

## Extensão — preflight de recuperação nativa (2026-10-24)

Após o incidente [ReqSys Actions #40062202879](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/40062202879), o mesmo workflow self-hosted do Desktop admite o modo `preflight` (default antigo `kick` preservado). Somente o proprietário pode solicitá-lo pelo comando exato `/reqsys run desktop-admin-broker-recovery-preflight` na issue #1705.

1. **Nenhum novo workflow:** reutilizar `.github/workflows/noteri-desktop-admin-broker-kick.yml`, sem ampliar a superfície de CI; modo de despacho fixo `preflight`.
2. Execução Risk 1 no host `DESKTOP-PDQK954`, via Python 3.12.10 pinado por SHA-256, regras canônicas por SHA, `session_launcher.py` e Command Gateway com worktree isolado e expected HEAD.
3. Inspecionar exclusivamente os dois runtimes persistentes autorizados, metadata source SHA/release/Python/run.py, tarefas `\\Automation\\ReqSysDesktopAdminBroker` e `\\Automation\\ReqSysDesktopControlPlaneWatchdog` via `schtasks /Query /XML`, S4U, boot trigger, run level e caminho exato.
4. Registrar somente booleanos e source SHA; `gh auth status` deve ignorar tokens temporários do workflow e nunca produzir stdout/stderr na evidência.
5. `NATIVE_REPAIR_ELIGIBLE_NOT_EXECUTED` significa que a tarefa precisa de reparo e existe elevação efetiva — **não** significa que foi reparada. `EXISTING_TASKS_AND_AUTH_READY` exige ambas as tarefas íntegras e `gh` local autenticado. Qualquer divergência é `BLOCKED_*`, falha fechada.
6. Proibido criar, alterar, executar ou remover tarefa no preflight; proibido UAC, segredos, reboot, RDC, produção ou alteração de branch protection. O reparador nativo continua ação Risk 3 separada, sujeita à autorização específica e readback independente.
7. Testes positivos e negativos obrigatórios: host divergente; metadata/release alterados; tarefa ausente; S4U alterado; ausência de auth; e um E2E físico do preflight vinculado ao SHA integrado antes de usá-lo como evidência para liberar reparo.
