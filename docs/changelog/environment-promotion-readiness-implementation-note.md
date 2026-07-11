# Nota de implementação — Promotion Readiness

Este incremento não executa deploy automático em DEV/STG/PROD.

Ele cria o contrato executivo que responde se os ambientes criados já possuem evidência suficiente para promoção produtiva. O deploy e os smokes por ambiente continuam sob o workflow existente:

- `.github/workflows/fly-environment-homologation-gate.yml`

O novo workflow:

- `.github/workflows/environment-promotion-readiness.yml`

consolida as evidências desses ambientes e bloqueia promoção para produção quando faltar DEV, STG ou PROD.

## Estado esperado inicialmente

Enquanto as evidências reais dos três ambientes não forem publicadas, a decisão correta é:

- `BLOCKED_FOR_PROD_PROMOTION`

Isso é intencional e seguro.
