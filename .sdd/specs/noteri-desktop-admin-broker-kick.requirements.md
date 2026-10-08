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
