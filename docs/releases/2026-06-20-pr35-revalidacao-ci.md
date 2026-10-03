# PR #35 — Revalidação de CI após correção dos gates

## Contexto

O PR #35 adiciona instruções operacionais para Cursor Cloud em `AGENTS.md` e não altera código produtivo.

O primeiro CI associado ao PR falhou por problemas transversais existentes na base de comparação na época:

- ordenação/importação no backend avaliada pelo `ruff`;
- import default inexistente no frontend para `src/services/api.js`.

Esses problemas foram corrigidos posteriormente na `main` pelo PR #38.

## Objetivo desta nota

Registrar a revalidação do PR #35 contra a base corrigida e disparar nova execução do CI sem mascarar quality gates.

## Critério de aceite

O PR #35 só deve sair de draft e ser considerado para merge quando o workflow `CI — ReqSys v2 Enterprise` concluir com sucesso nos jobs:

- `Backend Lint & Security (ruff + pip-audit + bandit)`;
- `Backend Tests + Coverage (pytest)`;
- `Frontend Build + Security Audit (Vite + npm audit)`;
- `Frontend Responsive E2E (Playwright)`.

## Governança

- Sem bypass de CI.
- Sem merge automático.
- Sem alteração de produção.
- Merge permitido somente após CI verde e revisão do escopo documental.
