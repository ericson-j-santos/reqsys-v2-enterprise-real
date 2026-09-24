# Desktop PC24x7 — reparo nativo do plano de controle

## Objetivo

Recuperar as tarefas governadas `ReqSysDesktopAdminBroker` e
`ReqSysDesktopControlPlaneWatchdog` quando os launchers Python/UAC existentes
falharem por dependência local ou instalação parcial, sem depender de RDC,
runner GitHub, SMB/WMI/WinRM remoto ou `pywin32`.

## Classificação

`gap_fix`.

## Escopo

- host único: `DESKTOP-PDQK954`;
- ambiente local/DEV;
- somente as instalações já materializadas em
  `%LOCALAPPDATA%\ReqSys\DesktopAdminBroker` e
  `%LOCALAPPDATA%\ReqSys\DesktopControlPlaneWatchdog`;
- nenhuma promoção para TEST/HML/STG/PROD.

## Requisitos

1. Usar somente Windows PowerShell 5.1+ e COM nativo `Schedule.Service`.
2. Não instalar pacote, módulo ou dependência adicional.
3. Falhar fechado se host, metadata, source SHA, release root, Python ou `run.py` divergirem do contrato.
4. Não aceitar parâmetros de usuário, host, task name, executável, path, segredo ou comando arbitrário.
5. Registrar somente:
   - `\Automation\ReqSysDesktopControlPlaneWatchdog` com AtStartup + S4U + run level limitado;
   - `\Automation\ReqSysDesktopAdminBroker` com AtStartup + S4U + highest.
6. Se não estiver elevado, solicitar UAC somente para o próprio script fixo.
7. Iniciar as duas tarefas somente após releitura independente do Task Scheduler confirmar AtStartup + S4U e o run level esperado.
8. Não acessar rede, GitHub API, secrets, produção, reboot, shutdown, RBAC ou credenciais.
9. Persistir evidência sanitizada em
   `%LOCALAPPDATA%\ReqSys\DesktopControlPlaneNativeRepair\last.json`.

## Critério de conclusão

A correção de código é considerada pronta quando:
- testes de guardrail passam;
- Pre-PR Readiness passa no HEAD exato;
- CI obrigatório fica verde;
- o runtime só é considerado recuperado após evidência local de ambas as tarefas e posterior pickup real do runner + RDC online.
