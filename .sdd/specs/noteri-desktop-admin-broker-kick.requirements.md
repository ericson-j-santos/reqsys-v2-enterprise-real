# Noteri → Desktop Admin Broker Kick

## Objetivo

Permitir que o runner governado do Noteri solicite somente o start da tarefa já existente `\Automation\ReqSysDesktopAdminBroker` no `DESKTOP-PDQK954`, sem GUI e sem depender do runner do Desktop.

## Requisitos

1. Origem fixa `Noteri`.
2. Destino fixo `DESKTOP-PDQK954`.
3. Tarefa fixa `\Automation\ReqSysDesktopAdminBroker`.
4. Única mutação permitida: `schtasks.exe /Run /S DESKTOP-PDQK954 /TN <task>`.
5. Proibidos `/Create`, `/Change`, `/Delete`, `/U`, `/P` e argumentos externos.
6. Nenhum segredo, reboot, deploy ou produção.
7. Evidência sanitizada como artifact.
8. Execução somente por workflow self-hosted do Noteri e comando exato no Authorized Actions Gateway.
9. A operação remota é acionada somente por `workflow_dispatch`; `pull_request`, `pull_request_target` e `push` não podem executar o RPC. Em PR, a validação ocorre apenas por testes de contrato/governança sem mutação remota.

## Critérios de aceite

- sucesso registra `EXISTING_DESKTOP_ADMIN_BROKER_RUN_REQUESTED`;
- acesso negado ou falha RPC termina fail-closed;
- `task_created_or_modified=false`;
- `credentials_supplied=false`;
- testes validam argv exato e ausência de credenciais.
