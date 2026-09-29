# Auto Public Runtime Evidence — PC24x7-only

## Contexto

O DEV canônico do ReqSys usa PC24x7 + locator assinado. O workflow automático não pode depender de Fly, de provider selecionável ou de URL estática.

## Requisitos

1. O `workflow_run` deve escutar `Main Post-Merge Validation`.
2. O caminho automático só avança quando o upstream conclui `success` em `main` e foi acionado por `workflow_dispatch`.
3. A URL DEV deve ser resolvida por `scripts/resolve_pc24x7_dev_locator.mjs`.
4. A URL resolvida deve usar HTTPS sob `*.trycloudflare.com`.
5. Qualquer `fly.io`/`fly.dev` deve falhar fechado.
6. Não usar `REQSYS_DEV_RUNTIME_PROVIDER`, `PC24X7_DEV_BASE_URL` ou `PC24X7_DEV_FRONTEND_URL` como fallback.
7. O dispatch automático deve usar `strict=true`, `publish_comment=false` e `ref=main`.
8. O token continua sendo somente `${{ github.token }}`, com `actions: write` e `contents: read`.

## Critérios de aceite

- upstream Fly ausente;
- locator assinado presente;
- rota PC24x7 validada e Fly rejeitado;
- credencial efêmera preservada;
- testes contratuais e gate DEV passam;
- `READY_FOR_PR=passed` e `behind_by=0` no HEAD exato.
