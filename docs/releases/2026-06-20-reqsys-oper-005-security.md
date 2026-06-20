# 2026-06-20 — REQSYS-OPER-005 — Segurança

## Regras de segurança

- Nenhum segredo deve ser enviado ao frontend.
- Nenhum dado pessoal deve ser retornado pelo endpoint.
- Detalhes técnicos devem ser mascarados.
- Integrações externas futuras devem ocorrer pelo backend.
- `correlation_id` deve acompanhar requisição e resposta.

## Validação inicial

A primeira fatia inclui teste automatizado que procura termos sensíveis no payload retornado pelo endpoint.

Refs #46
