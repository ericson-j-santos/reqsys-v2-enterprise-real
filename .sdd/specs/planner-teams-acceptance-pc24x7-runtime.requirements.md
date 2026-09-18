# Planner → Teams DEV — Runtime PC24x7

## Requisito 1 — origem do runtime
O aceite DEV deve consumir a URL pública governada do PC24x7 por meio de `PC24X7_DEV_BASE_URL`, sem endpoint Fly.io fixo.

## Requisito 2 — falha fechada
A execução deve parar antes da autenticação/E2E quando a URL estiver ausente, não usar HTTPS ou apontar para `*.fly.dev`.

## Requisito 3 — evidência de disponibilidade
O workflow deve validar `/api/runtime/health` no runtime PC24x7 antes de executar o aceite Planner → Power Automate → Teams.

## Critérios de aceite (Acceptance Criteria)
1. O workflow não contém `https://reqsys-api-dev.fly.dev`.
2. `API_URL` é obtida de `vars.PC24X7_DEV_BASE_URL`.
3. URL vazia, sem HTTPS ou Fly.io falha de forma explícita.
4. O health público PC24x7 é validado antes do E2E.
5. O teste contratual automatizado e o Pre-PR Readiness devem aprovar o incremento.
