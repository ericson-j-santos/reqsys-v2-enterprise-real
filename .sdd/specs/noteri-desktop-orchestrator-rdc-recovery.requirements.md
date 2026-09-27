# OPS-GAP-1818 — RDC recovery via Desktop Orchestrator

## Objetivo

Usar o plano de controle já vivo em `DESKTOP-PDQK954:8787` para reiniciar a
task existente e validada do Remote Desktop Commander, sem depender do runner
GitHub do Desktop e sem usar RPC remoto, WMI, C$, GUI ou shell remoto.

## Contrato

- origem física: `Noteri`;
- execução: Session Launcher → Command Gateway;
- target fixo: `DESKTOP-PDQK954:8787`;
- capability: somente `host.rdc.recover.v1`;
- task host-side: somente `\Automation\RemoteDesktopCommander`;
- launcher: somente `C:\RemoteDesktopCommander\start-remote-desktop-commander.cmd`;
- `force_restart=true` fixo para eliminar processo/tarefa stale;
- risk 2, uma tentativa, timeout limitado;
- replay obrigatório sem redispatch;
- controle negativo de work item inexistente;
- leitura independente do work item terminal;
- o resultado do Orchestrator não prova transporte RDC online: essa prova é
  feita depois pelo controlador externo.

## Fora de escopo

Sem reboot, criação/edição de tarefa, credenciais, produção, deploy, shell remoto,
WMI, C$, RPC Task Scheduler remoto ou bypass do Command Gateway.

## Aceite

1. testes positivos e negativos verdes no SHA exato;
2. worker Desktop fresco/online/autenticado e capability `host.rdc.recover.v1`;
3. work item termina `CONCLUÍDO` com task/launcher exatos;
4. replay é idempotente e não redispatcha;
5. readback independente do work item confirma o mesmo resultado;
6. artifact é gravado fora do worktree;
7. Remote Desktop Commander é verificado independentemente após o recovery.
