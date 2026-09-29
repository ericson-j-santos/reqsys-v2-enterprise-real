# Auto Public Runtime Evidence

## Objetivo

Executar `Public Runtime Evidence Gate` para o DEV PC24x7 após a validação pós-merge fail-closed do SHA atual, sem PAT e sem fallback Fly.

## Quando executa

1. Automaticamente somente quando `Main Post-Merge Validation` concluir `success` em `main` e o upstream tiver sido acionado por `workflow_dispatch`.
2. Manualmente por `workflow_dispatch`, quando necessário.

Runs agendados/report-only do `Main Post-Merge Validation` não disparam esta cadeia.

## Roteamento DEV

- o runtime é resolvido por `scripts/resolve_pc24x7_dev_locator.mjs`;
- a URL deve ser HTTPS sob `*.trycloudflare.com`;
- `fly.io` e `fly.dev` são rejeitados de forma fail-closed;
- não são usados `REQSYS_DEV_RUNTIME_PROVIDER`, `PC24X7_DEV_BASE_URL` ou `PC24X7_DEV_FRONTEND_URL` como fallback estático.

## Credencial

O fluxo usa somente `GITHUB_TOKEN` efêmero, com `actions: write` e `contents: read`. Não usa PAT nem chave de GitHub App.

## Comportamento automático

O dispatch para `public-runtime-evidence.yml` usa `strict=true`, `publish_comment=false`, `ref=main` e provider efetivo `pc24x7`.

## Critério de aceite

- upstream fail-closed no SHA atual;
- locator assinado resolvido;
- URL PC24x7 validada e Fly rejeitado;
- `Public Runtime Evidence Gate` disparado;
- nenhum segredo de longa duração usado.
