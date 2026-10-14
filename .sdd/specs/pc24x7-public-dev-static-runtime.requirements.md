# PC24x7 Public DEV — runtime estático e same-SHA

## Objetivo

Eliminar a abertura extremamente lenta do ReqSys DEV público e impedir falso verde de runtime desatualizado.

## Requisitos

1. O ambiente alvo é exclusivamente DEV no host exato DESKTOP-PDQK954.
2. O repositório do runtime deve ser sincronizado apenas por fast-forward até o SHA exato autorizado da main.
3. O frontend público deve usar o build de produção do Vite e ser servido por Nginx; Vite/HMR permanece permitido apenas no desenvolvimento local.
4. O gateway público deve encaminhar o frontend para a porta 80 e bloquear explicitamente /@vite/client, /src/ e /@id/.
5. A API deve publicar GITHUB_SHA igual ao SHA esperado.
6. A reconciliação deve recriar somente api, frontend e nginx do projeto DEV observado, preservando banco, KB, HML, STG e PROD.
7. O locator assinado só pode ser publicado quando /api/health, /api/runtime/health, /api/runtime/readiness e /api/runtime/build-info retornarem HTTP 200.
8. O locator deve falhar fechado quando /@vite/client estiver exposto ou quando /task-console não estiver disponível.
9. A prova física deve ser seguida por smoke público independente, no mesmo SHA, validando frontend estático, asset real, health/readiness/build-info e controle negativo de Vite.
10. Nenhum segredo deve ser registrado em log, issue ou artifact.
11. Nenhum deploy ou promoção de HML/STG/PROD integra este incremento.
12. O Authorized Actions Gateway deve aceitar somente o comando exato /reqsys run pc24x7-public-dev-reconcile.

## Critérios de aceite

- Pre-PR Readiness verde no HEAD exato e behind_by=0.
- Testes de contrato e Compose passam.
- Runner PC24x7 adquire o workflow e a reconciliação física termina verde.
- build_sha público é idêntico ao SHA do workflow.
- /task-console retorna HTML estático com /assets/ e sem /src/main.js.
- /@vite/client retorna 404.
- Um asset publicado retorna HTTP 200 por leitura externa independente.
- Locator é republicado somente após todos os critérios locais e públicos.
- Repetição no mesmo SHA permanece idempotente e não cria stack paralela.


## Contenção da rota legada sem rollback atestado — 14/10/2026

O E2E físico #38613970486 no SHA `920e90f1ce4725db31177e01baaca182a2ef4800`
identificou `deploy_readiness_sha_mismatch`, sem provar a versão instalada nem a
prontidão do PostgreSQL. O modo `public-static` anterior podia executar Compose
e publicação do locator sem Session Launcher/Command Gateway e sem confirmação
de backup/rollback independente. A prevenção imediata bloqueia esse modo
**antes do OIDC, Compose e locator** e também bloqueia a função Python de
reconciliação legada quando não existe um runtime portátil já verificado.

Critério para remover a quarentena (incremento distinto, sem bypass):
- sessão `SESSION_LAUNCH_OK` e Gateway fixados no mesmo SHA;
- inventário de host/Compose/projeto/volumes e digest das imagens anteriores;
- backup PostgreSQL protegido e restauração isolada com prova de conteúdo,
  contagens, esquema e sequências, sem modificar a origem;
- rollback de api/frontend/nginx ensaiado inclusive com API candidata indisponível;
- CI detectando falta de qualquer prova, concorrência, replay e SHA divergente;
- autorização explícita do owner para deploy DEV e E2E físico posterior.

Este incremento não executa backup físico, restore, Docker Compose ou deploy.

## Primeiro incremento após a quarentena — inventário governado read-only

O modo `public-static` passa a utilizar Session Launcher/Command Gateway da mesma forma que o `study-mode`, com checkout da regra fixada, preflight de versão do runner, SHA exato, reserva de worktree, sessão e inspeção somente leitura por `scripts/diagnose_pc24x7_public_dev.py --stdout-only` (`python -B`, risco 1). A coleta do inventário comprova apenas metadados permitidos do Docker DEV e produz um receipt público sanitizado sem o JSON bruto do host. A quarentena anterior permanece obrigatória **depois** do inventário e **antes** de OIDC, Compose, publicação do locator ou aplicação de configuração. Se o inventário falhar, a execução também falha fechada. Não há backup físico nesta fase.

A remoção futura da quarentena dependerá de implementação e prova independente de backup PostgreSQL real, restauração em cópia isolada, imagens api/frontend/nginx para rollback, controle de concorrência, autorização Risk 3 específica de host e DEV, cenário negativo e E2E same-SHA. Os testes estruturais detectam bypass da quarentena, desativação da sessão e elevação indevida de risco da leitura. Referência de continuidade: issue #2546, run físico #38613970486.
