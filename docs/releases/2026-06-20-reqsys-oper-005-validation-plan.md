# 2026-06-20 — REQSYS-OPER-005 — Plano de validação

## Validações esperadas no CI

- Backend lint e segurança.
- Backend tests e coverage.
- Frontend build e audit.
- Frontend responsive E2E.

## Validações específicas

- `GET /monitoramento-operacional` retorna 200.
- Resposta usa envelope padrão.
- `correlation_id` é preservado.
- Estado geral é calculado corretamente.
- Resposta não contém campos sensíveis.
- Tela renderiza em layout responsivo.

Refs #46
