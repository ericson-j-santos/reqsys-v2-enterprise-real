# Teams Gateway Control Center — recuperação de código

## Objetivo
Preservar em controle de versão o artefato atualmente recuperável do projeto Teams Gateway Control Center sem alterar a implementação canônica do ReqSys.

## Requisitos

1. O artefato recuperado deve permanecer em `tools/teams-gateway-control-center-site-recovery/index.html`.
2. A proveniência deve registrar o projeto `sites-project://appgprj_6a615cfc7c9881918dee3af3303d631a` e a fonte recuperada.
3. O estado deve ser explicitamente classificado como recuperação parcial enquanto o snapshot integral do projeto Sites não estiver acessível.
4. A recuperação não pode declarar deploy, alteração de runtime ou alteração de produção.
5. O HTML deve continuar identificável como Teams Gateway Control Center e manter os endpoints de status necessários para inspeção offline.
6. Nenhum segredo deve ser adicionado intencionalmente ao artefato.

## Critérios de aceite (Acceptance Criteria)

1. O HTML recuperado existe e contém o título `Teams Gateway Control Center`.
2. O HTML contém a referência `/v1/teams-gateway/status`.
3. `SOURCE-METADATA.json` identifica `partial_source_recovery`.
4. Os metadados declaram `secrets_included=false`, `runtime_changed=false`, `deployment_performed=false` e `production_touched=false`.
5. O teste automatizado específico da recuperação passa.
6. A repetição do teste sobre o mesmo conteúdo produz o mesmo resultado.
