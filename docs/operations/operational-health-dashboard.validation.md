# Validation Plan — Operational Health Dashboard Governance

## Validações locais/documentais

- Conferir existência do documento principal.
- Conferir existência do schema JSON.
- Conferir existência do exemplo JSON.
- Conferir existência do runbook.
- Conferir existência da ADR.
- Conferir existência do workflow.

## Validações GitHub Actions

- `Operational Health Dashboard` deve validar termos obrigatórios.
- O workflow deve gerar artifact review-only.
- O workflow deve executar em `pull_request`.
- O workflow deve executar em `workflow_dispatch`.
- O workflow deve executar em `push` para `main` quando houver alteração nos arquivos do escopo.

## Validações de segurança

- Nenhum deploy.
- Nenhuma alteração produtiva.
- Nenhuma alteração de permissões administrativas.
- Nenhuma mutação automática de PR.

## Resultado esperado

`OPERATIONAL_HEALTH_DASHBOARD_READY`.
