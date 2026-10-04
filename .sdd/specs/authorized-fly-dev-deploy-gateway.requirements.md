# Gateway autorizado — publicação Fly DEV

## Objetivo

Permitir publicar o ambiente DEV do ReqSys pelo Authorized Actions Gateway usando somente um comando exato, sem browser interativo, workflow arbitrário, parâmetros livres ou acesso a STG/HML/PROD.

## Requisitos

1. O gateway deve aceitar somente o comando exato `/reqsys run fly-dev-fast-deploy`.
2. O comando deve permanecer restrito à issue #1705 e ao ator `ericson-j-santos`.
3. O workflow alvo deve ser fixo em `fly-dev-fast-deploy.yml`.
4. A referência deve ser fixa em `main`.
5. O input deve ser fixo em `deploy=true`.
6. Nenhum nome de workflow, branch, ambiente ou input arbitrário pode vir do comentário.
7. O gateway deve manter permissões mínimas: `actions: write` e `contents: read`.
8. O fluxo não deve ler segredos nem tocar STG/HML/PROD.
9. A evidência sanitizada deve registrar o SHA da main e o run disparado.
10. A publicação só conta como válida após `/api/runtime/build-info` confirmar o mesmo SHA.
11. O workflow `fly-dev-fast-deploy.yml` deve ser exclusivamente uma contingência manual por `workflow_dispatch`; `push`, `schedule` ou outro gatilho automático não podem autorizar deploy Fly DEV.
12. Mesmo que outro gatilho seja reintroduzido por engano, o preflight deve falhar fechado com `should_deploy=false` fora de `workflow_dispatch` com `deploy=true`.

## Critérios de aceite

- teste de contrato comprova comando, workflow, ref e input exatos;
- comandos não allowlisted continuam fail-closed;
- `production_touched=false` permanece na evidência;
- workflow disparado deve publicar somente DEV;
- workflow Fly DEV não possui gatilho automático e o teste de contrato falha se `push` ou `schedule` reaparecer;
- após deploy, o runtime DEV deve informar o SHA esperado antes de qualquer aceite WSJF;
- bootstrap WSJF e aceite real devem ser reexecutados somente depois do same-SHA.
