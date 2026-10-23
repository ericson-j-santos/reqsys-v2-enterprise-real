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

## Segundo incremento — cutover recuperável governado — 22/10/2026

A quarentena deixa de ser um `throw` incondicional somente quando a mesma execução
manual produz e valida as seguintes provas antes de OIDC/Compose/locator:

- Session Launcher e Command Gateway fixados no SHA de `main` para bootstrap e
  inventário; toda mutação passa pela rota separada `owner_risk3_gateway.py`,
  classificada como Risk 3 e limitada a host/DEV;
- dispatch vinculado ao comentário exato e recente do owner na issue `#1705` e
  ao SHA de `main` capturado pelo gateway, com readback antes do checkout;
- captura selada das imagens correntes de api/frontend/nginx e criação de tags de
  rollback com readback do image ID;
- snapshots privados e imutáveis, na ordem observada, somente dos manifests
  Compose por serviço; cadeias distintas após recriação parcial governada são
  preservadas e reaplicadas separadamente, sem reordenar ou sintetizar uma cadeia
  comum; env-files continuam no local original e não são duplicados;
- `pg_dump` da base DEV executado dentro do contêiner PostgreSQL observado, mantido
  em disco apenas como ciphertext DPAPI de escopo do usuário;
- restauração do dump em contêiner descartável da mesma imagem PostgreSQL, sem rede,
  comparando fingerprint de esquema, contagem de todas as tabelas e sequências;
- manifesto privado íntegro com fingerprint externo, nunca incluído em artifact;
- deploy executado pelo Owner Risk 3 Gateway e condicionado à revalidação do
  manifesto;
- em falha do cutover, rollback automático das três imagens, inclusive quando a API
  candidata estiver indisponível, preservando as validações físicas de host, raiz,
  projeto, cardinalidade e imagens;
- publicação do locator somente depois do runtime local same-SHA e dos controles de
  frontend estático; smoke público independente permanece obrigatório.

O backup cifrado, manifesto e override de rollback permanecem no diretório privado
`.reqsys-recovery` do runtime, junto aos snapshots Compose necessários para que o
fast-forward não invalide o rollback. Artifacts públicos contêm apenas flags sanitizadas,
fingerprints e resultado. O fluxo não restaura a base ativa automaticamente: api,
frontend e nginx são os únicos serviços recriados pelo deploy; qualquer divergência
da base após rollback falha fechada e exige intervenção específica. HML/STG/PROD,
segredos, rotação de credenciais, pruning de imagem e mudança de rede continuam fora
do escopo.

O Command Gateway geral continua recusando Risk 3. A rota do owner exige a
configuração privada do modo temporário `standard_gold_development` ainda válida,
worktree limpo, script Python rastreado no SHA da sessão, timeout máximo de 900 s e
auditoria por hash. Ausência ou expiração dessa configuração bloqueia antes de
qualquer mutação; ela não é ativada automaticamente pelo workflow.

Se o inventário read-only falhar, o workflow deve continuar fail-closed e publicar
um receipt sanitizado com `status=inventory_blocked` e `reason_code` pertencente a
uma allowlist fixa. O receipt não pode incluir stdout/stderr, IDs ou metadados de
contêiner, paths privados ou credenciais. A ausência de inventário válido continua
bloqueando backup, OIDC, Compose, locator e qualquer outra mutação.

No Windows, a verificação do alvo Docker aceita somente os dois endpoints locais
fixos do Docker Desktop (`dockerDesktopLinuxEngine` e `docker_engine`). Overrides
por `DOCKER_HOST`/`DOCKER_CONTEXT`, TCP e qualquer named pipe não allowlisted
continuam bloqueados. Independentemente do contexto local ativo, toda leitura do
inventário permanece explicitamente presa ao pipe Linux
`dockerDesktopLinuxEngine`.

## Terceiro incremento — fontes Compose por serviço — 23/10/2026

O run físico `39965334691` falhou fechado antes de OIDC/deploy com a categoria
sanitizada `recovery_source_invalid`. A análise somente leitura do código encontrou
uma incompatibilidade determinística: o contrato já testado de recriação pública
aceita que a API tenha uma cadeia Compose própria após atualização parcial, desde
que frontend e nginx comprovem o overlay público, enquanto a captura de rollback
recusava qualquer diferença entre os três serviços com
`compose_config_order_mismatch`.

O manifesto privado passa ao schema 3 e sela, por serviço, a ordem de manifests e
env-files observada. Arquivos Compose são copiados para snapshots privados,
imutáveis e deduplicados; valores de env-file continuam sem leitura ou cópia. O
rollback agrupa serviços somente quando as cadeias são idênticas. Quando divergem,
cada serviço é restaurado com sua cadeia exata, sempre com `--no-build`,
`--no-deps`, imagem imutável verificada e o mesmo override de rollback. Manifestos
schema 2 com cadeia única permanecem aceitos para compatibilidade.

Este incremento não executa captura física, backup, Docker Compose, deploy, locator
ou E2E. Nova tentativa física continua condicionada a merge governado, validação
pós-merge e autorização owner específica no SHA então vigente.
