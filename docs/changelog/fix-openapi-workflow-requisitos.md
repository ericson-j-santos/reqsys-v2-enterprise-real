# fix(openapi): rotas de workflow governado de requisitos

## Contexto

Após o merge da PR #708, o workflow `OpenAPI Semantic Diff` acusou drift `missing_in_openapi` para as novas rotas do backend:

- `GET /api/requisitos/{param}/workflow`
- `POST /api/requisitos/{param}/transicao`

O mesmo artefato também apontou drifts recorrentes em rotas runtime públicas já existentes.

## Correção

Atualizado o contrato estático `docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json` para registrar:

- workflow governado de requisitos;
- transição governada de requisitos;
- workspace operacional de requisitos;
- rotas runtime de readiness, liveness, metrics, operational mesh e evidências.

## Validação esperada

O gate `OpenAPI Semantic Diff` deve deixar de reportar `missing_in_openapi` para as rotas adicionadas pela PR #708.
