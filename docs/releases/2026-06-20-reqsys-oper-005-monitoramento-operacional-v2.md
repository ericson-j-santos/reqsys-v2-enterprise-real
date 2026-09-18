# 2026-06-20 — REQSYS-OPER-005 — Monitoramento operacional v2

## Resumo

Recriada fatia limpa para `/monitoramento-operacional`, reduzindo ruído e mantendo somente arquivos essenciais.

## Alterações

- Endpoint backend com envelope padrão, `schema_version`, `correlation_id`, ambiente normalizado e resumo operacional.
- Registro do router no `backend/app/main.py`.
- Testes de contrato, correlação, frentes prioritárias e precedência de estado.
- View frontend com cards, filtro por estado e tabela analítica.
- Registro de rota frontend e item no menu principal.
- Documentação de API.
- ADR.

## Pendências refletidas no snapshot

- GovBI IA: consulta ainda não estabilizada.
- Dashboard para Analítico filtrado: padrão de deep link e filtros ainda pendente.
- Planner: contrato operacional ainda pendente.
- Pipeline operacional: evidências automatizadas ainda pendentes.
- Monitoramento operacional: primeira fatia funcional em validação.

## Gate

PR deve permanecer em draft até CI verde. CI verde é condição necessária, mas não suficiente para merge.

Refs #46