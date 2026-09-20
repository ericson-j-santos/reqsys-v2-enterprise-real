# Aceite WSJF DEV — Runtime PC24x7

## Requisito 1 — runtime canônico
O aceite real WSJF DEV deve usar exclusivamente `vars.PC24X7_DEV_BASE_URL` e `vars.PC24X7_DEV_FRONTEND_URL`.

## Requisito 2 — falha fechada
A execução deve bloquear antes dos testes se uma URL estiver ausente, não usar HTTPS ou apontar para Fly.io.

## Requisito 3 — same-SHA
O SHA do workflow deve ser idêntico ao SHA retornado por `/api/runtime/build-info` no PC24x7 DEV.

## Requisito 4 — saúde pública
O gate deve validar `/api/runtime/health` e o frontend público antes de prosseguir.

## Requisito 5 — integrações Microsoft
Graph e Power Platform devem ser comprovados por GitHub OIDC / Workload Identity Federation, sem `client_secret`, `flyctl` ou credencial de deploy Fly.

## Requisito 6 — efeito de negócio
A prova Planner → Power Automate → `tbDemandas` permanece real, idempotente, preserva os campos locais e proíbe writeback indevido ao Planner.

## Requisito 7 — evidência final
Somente `accepted=true` e `one_hundred_percent_allowed=true` no mesmo SHA publicado permitem declarar 100%.

## Critérios de aceite
1. Nenhum endpoint, credential-id ou comando Fly existe em `user-journey-acceptance-dev.yml`.
2. O E2E contínuo Planner → Teams não depende de `Fly DEV Fast Deploy`.
3. URLs PC24x7 inválidas falham fechado.
4. Graph e Power Platform usam OIDC federado.
5. Testes de contrato e Pre-PR Readiness ficam verdes.
