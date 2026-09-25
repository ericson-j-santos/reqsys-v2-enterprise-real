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
