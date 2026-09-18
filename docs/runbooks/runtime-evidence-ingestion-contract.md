# Runtime Evidence Ingestion Contract

## Objetivo

Preparar o ReqSys para ingerir historicamente os artifacts `public-runtime-evidence` gerados pelo GitHub Actions sem alterar o contrato strict público.

## Endpoints adicionados

```text
GET /api/runtime/evidence/artifacts
GET /api/runtime/evidence/incidents
GET /api/runtime/evidence/scorecard
```

## Escopo deste incremento

Esta versão entrega contrato governado e stubs operacionais para a futura hidratação com artifacts reais.

## Decisões

- Não alterar `/health`, `/api/runtime/health`, `/api/runtime/readiness` ou `/api/runtime/liveness`.
- Não depender de token GitHub em runtime público.
- Não expor secrets, PAT, JWT ou dados sensíveis.
- Manter ingestão real como próximo incremento desacoplado.

## Próxima evolução

Conectar um job interno ou worker governado para baixar artifacts `public-runtime-evidence`, normalizar snapshots e alimentar os endpoints de analytics com histórico real.
