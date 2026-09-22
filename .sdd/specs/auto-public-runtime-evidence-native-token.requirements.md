# Auto Public Runtime Evidence — roteamento atual de runtime

## Contexto

A correção anterior eliminou o HTTP 422 da GitHub App usando `GITHUB_TOKEN` efêmero. A validação pós-merge mostrou dois resíduos de arquitetura:

1. o workflow automático ainda escutava `ReqSys Fly Runtime P0`, que não é mais o caminho canônico de validação DEV;
2. o modo automático fixava `https://reqsys-api.fly.dev`, embora `REQSYS_DEV_RUNTIME_PROVIDER=pc24x7` seja suportado e já usado pelo fluxo de promoção atual.

## Requisitos

1. O gatilho `workflow_run` deve escutar `Fly Automatic Environment Promotion`.
2. Execução automática só pode avançar quando o upstream terminar `success` em `main`.
3. O provider automático deve vir de `vars.REQSYS_DEV_RUNTIME_PROVIDER`, aceitando somente `fly` ou `pc24x7`.
4. Para `fly`, usar a URL canônica `https://reqsys-api.fly.dev`.
5. Para `pc24x7`, exigir `vars.PC24X7_DEV_BASE_URL`, não vazio e HTTPS.
6. Provider inválido ou URL PC24x7 ausente/insegura deve falhar fechado antes do dispatch.
7. O disparo automático deve usar `strict=true`, `publish_comment=false` e `ref=main`.
8. O fluxo manual deve preservar os inputs explícitos do operador.
9. O token deve continuar sendo somente `${{ github.token }}`, com `actions: write` e `contents: read`.

## Critérios de aceite

1. O teste contratual prova que o upstream antigo não está mais configurado.
2. O teste contratual prova os ramos `fly` e `pc24x7`.
3. O teste prova fail-closed para provider inválido, URL PC24x7 vazia e URL não HTTPS.
4. O teste prova `strict=true` no caminho automático.
5. O contrato de token efêmero continua verde.
6. O SDD Gate passa no HEAD exato.
7. O Pre-PR Readiness retorna `READY_FOR_PR=passed` e `behind_by=0`.
