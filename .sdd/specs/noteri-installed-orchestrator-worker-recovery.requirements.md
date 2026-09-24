# Recuperação do worker instalado do Engineering Orchestrator no Noteri

## Objetivo

Restaurar em DEV o worker `noteri` do Engineering Orchestrator quando o plano de controle do Desktop está saudável, mas o heartbeat do Noteri está stale/offline, sem depender de RDC, GUI, segredo novo ou alteração administrativa.

## Classificação

`gap_fix`.

## Requisitos

- executar somente no runner `[self-hosted, Windows, X64, noteri, reqsys-dev]`;
- executar somente no host físico `Noteri`;
- não aceitar inputs arbitrários de host, endpoint, comando ou caminho;
- usar apenas o runtime instalado em `C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime`;
- validar `mode=worker`, `worker_id=noteri` e endpoint `http://DESKTOP-PDQK954:8787`;
- falhar fechado se o runtime instalado não contiver a capability `host.profile.set.v1`;
- remover `RUNNER_TRACKING_ID` antes de iniciar o supervisor persistente;
- exigir leitura independente do registro `/v1/workers` com um único Noteri fresh, controller_online, auth_valid, perfil NORMAL/ESTUDO e capability `host.profile.set.v1`;
- publicar somente evidência sanitizada;
- não criar/alterar/excluir tarefa do Task Scheduler;
- não tocar produção, segredo, RDC, reboot, deploy ou branch protegida;
- `pull_request` não pode executar código no runner self-hosted; o E2E físico pré-merge usa push canônico do owner.

## Critérios de aceite

1. testes unitários positivos e negativos verdes;
2. self-hosted governance verde;
3. workflow vinculado ao SHA exato da branch;
4. artifact físico com `ok=true`, `workflow_sha_verified=true`, `after.operational=true` e `after.profile_task_capable=true`;
5. E2E funcional do Modo Estudo repetido após a recuperação;
6. estado final do perfil restaurado para NORMAL pelo reconciliador funcional.
