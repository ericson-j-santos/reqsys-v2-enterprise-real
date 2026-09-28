# Aceite WSJF DEV — Runtime PC24x7

## Requisito 1 — runtime canônico
O aceite real WSJF DEV deve resolver o runtime vigente exclusivamente por
`scripts/resolve_pc24x7_dev_locator.mjs`, validando o locator assinado.
`vars.PC24X7_DEV_BASE_URL` e `vars.PC24X7_DEV_FRONTEND_URL` não podem ser
fonte operacional desse fluxo.

## Requisito 2 — falha fechada
A execução deve bloquear antes dos testes quando o locator estiver ausente,
expirado, com assinatura inválida, ambiente divergente ou URL fora de
`https://*.trycloudflare.com`. Fly.io permanece proibido.

## Requisito 3 — same-SHA
O SHA do workflow deve ser idêntico ao SHA retornado por `/api/runtime/build-info` no PC24x7 DEV.

## Requisito 4 — saúde pública e same-origin
O gate deve reaproveitar o mesmo `selected_url` do locator como API e frontend,
validar `/api/runtime/health` e o frontend público nesse mesmo host antes de
prosseguir.

## Requisito 5 — integrações Microsoft
Graph e Power Platform devem ser comprovados por GitHub OIDC / Workload Identity Federation, sem `client_secret`, `flyctl` ou credencial de deploy Fly.

## Requisito 6 — efeito de negócio
A prova Planner → Power Automate → `tbDemandas` permanece real, idempotente, preserva os campos locais e proíbe writeback indevido ao Planner.

## Requisito 7 — evidência final
Somente `accepted=true` e `one_hundred_percent_allowed=true` no mesmo SHA publicado permitem declarar 100%.

## Critérios de aceite
1. Nenhum endpoint, credential-id ou comando Fly existe em `user-journey-acceptance-dev.yml`.
2. O E2E contínuo Planner → Teams não depende de `Fly DEV Fast Deploy`.
3. Locator inválido, expirado, não assinado ou fora do domínio governado falha fechado.
4. API e frontend são fixados no mesmo `selected_url` resolvido durante toda a execução.
5. As variáveis estáticas `PC24X7_DEV_BASE_URL` e `PC24X7_DEV_FRONTEND_URL` não aparecem no workflow de aceite.
6. Graph e Power Platform usam OIDC federado.
7. Testes de contrato e Pre-PR Readiness ficam verdes no SHA exato.
8. Após integração em `main`, uma nova execução do aceite ultrapassa a resolução/conectividade do runtime no SHA integrado.
