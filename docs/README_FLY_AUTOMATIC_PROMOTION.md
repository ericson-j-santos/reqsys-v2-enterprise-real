# Promoção automática Fly

Entrada principal: `.github/workflows/fly-automatic-environment-promotion.yml`.

Contratos:

- `docs/contracts/fly-automatic-environment-promotion.md`
- `docs/contracts/fly-automatic-environment-promotion.schema.json`
- `docs/contracts/fly-environment-state-capture.schema.json`

Arquitetura:

- `docs/architecture/fly-automatic-promotion-flow.md`

A operação é fail-closed, promove somente o SHA atual da `main` e nunca ignora o BACEN Production Hard Gate.
