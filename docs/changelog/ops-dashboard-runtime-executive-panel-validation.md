# Ops Dashboard — Runtime Executive Panel Validation

## Contexto

O `runtime-executive-index.json` já é gerado e consumido pelo Ops Dashboard. Este incremento adiciona uma validação automática para garantir que o painel executivo esteja efetivamente exposto no `index.html` e conectado ao contrato JSON correto.

## Entrega

- Novo script offline/read-only: `scripts/validate_ops_dashboard_runtime_executive_panel.py`.
- Validação dos IDs HTML do painel Runtime Executive.
- Validação do contrato mínimo de `docs/ops-dashboard/data/runtime-executive-index.json`.
- Integração da validação no workflow `.github/workflows/ops-dashboard.yml`.

## Risco

Baixo. Não altera runtime produtivo, deploy, secrets nem contratos de API. Incremento apenas reforça governança do dashboard estático.

## Próximo incremento recomendado

Adicionar uma página dedicada `runtime-executive.html` com foco executivo para produção, consumindo o mesmo `runtime-executive-index.json`.
