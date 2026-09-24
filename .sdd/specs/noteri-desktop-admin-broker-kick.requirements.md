# Desktop Admin Broker — recuperação governada

## Objetivo

Recuperar a tarefa já existente `\Automation\ReqSysDesktopAdminBroker` no
`DESKTOP-PDQK954` sem GUI, sem RDC e sem criar ou alterar tarefa.

A solução mantém duas rotas explícitas:

1. **Noteri remoto/manual** — somente por `workflow_dispatch`, usando o runner
   governado do Noteri e RPC fixo para o Desktop.
2. **Desktop local/branch de prova** — somente em branch isolada
   `fix/noteri-desktop-admin-broker-kick-*`, usando o runner legado do próprio
   Desktop e `schtasks.exe /Run /TN <task>` local, sem `/S`.

## Classificação

`gap_fix`, ambiente local/DEV.

## Requisitos

1. A tarefa é fixa: `\Automation\ReqSysDesktopAdminBroker`.
2. A rota remota tem origem fixa `Noteri` e destino fixo
   `DESKTOP-PDQK954`.
3. A rota local exige host exato `DESKTOP-PDQK954`.
4. A única mutação permitida é solicitar o start da tarefa existente.
5. São proibidos `/Create`, `/Change`, `/Delete`, `/U`, `/P` e
   argumentos externos.
6. A rota local não pode usar `/S`, rede, credencial ou RPC remoto.
7. Nenhum segredo, reboot, deploy, promoção ou produção.
8. Toda execução técnica deve passar por Session Launcher com estado validado e,
   depois, Command Gateway em worktree isolado.
9. A rota remota só pode executar em `workflow_dispatch`; `push`,
   `pull_request` e `pull_request_target` não podem executar o RPC remoto.
10. O `push` permitido para prova local deve ficar restrito ao padrão
    `fix/noteri-desktop-admin-broker-kick-*`.
11. O job local deve usar somente
    `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
12. Um watchdog hospedado deve encerrar a prova local após 60 segundos sem
    pickup do runner físico.
13. Toda evidência deve ser sanitizada e vinculada ao SHA/correlation_id da
    execução.
14. A branch de prova não é evidência de promoção e não deve ser mergeada até
    existir E2E positivo no Desktop no mesmo SHA.

## Critérios de aceite

- rota remota bem-sucedida registra
  `EXISTING_DESKTOP_ADMIN_BROKER_RUN_REQUESTED`;
- rota local bem-sucedida registra
  `EXISTING_DESKTOP_ADMIN_BROKER_LOCAL_RUN_REQUESTED`;
- acesso negado, runner indisponível, host divergente ou falha do Task Scheduler
  terminam fail-closed;
- `task_created_or_modified=false`;
- `credentials_supplied=false`;
- testes validam argv exato e ausência de credenciais/RPC na rota local;
- Session Launcher e Command Gateway são exercitados antes da mutação;
- E2E positivo exige pickup no `DESKTOP-PDQK954` e solicitação local de start
  no mesmo SHA.
