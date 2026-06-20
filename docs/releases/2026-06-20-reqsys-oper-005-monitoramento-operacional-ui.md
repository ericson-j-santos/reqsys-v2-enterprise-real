# 2026-06-20 — REQSYS-OPER-005 — Painel inicial de monitoramento operacional

## Resumo

Adicionada base visual inicial para `/monitoramento-operacional` no frontend do ReqSys.

## Alterações

- Criada view `MonitoramentoOperacionalView.vue`.
- Registrada rota `/monitoramento-operacional`.
- Adicionados cards de estado geral, bloqueios, pendências e total de itens.
- Adicionada tabela analítica de itens monitorados.
- Adicionados filtros por estado e severidade com query string para deep link.

## Observações

A tela consome o endpoint `/monitoramento-operacional`. A coleta real de GitHub PRs, GitHub Actions e histórico persistido permanece como próximo incremento.

Refs #46
