# Runtime Public JSON Contracts

## Objetivo

Versionar uma superfície pública mínima e governada para evidência operacional do ReqSys.

Este incremento complementa o `Public Runtime Evidence Gate` e permite que operadores, automações e futuros painéis consultem contratos JSON estáveis sem depender de scraping ou inferência de UI.

## Endpoints adicionados

```text
GET /api/runtime/contracts
GET /api/runtime/version
GET /api/runtime/build-info
GET /api/runtime/dependencies
```

## Contrato strict público vigente

O contrato público obrigatório continua limitado aos endpoints de disponibilidade:

```text
GET /health
GET /api/runtime/health
GET /api/runtime/readiness
GET /api/runtime/liveness
```

## Critérios de aceite

| Critério | Estado esperado |
|---|---|
| Endpoints JSON | HTTP 200 |
| Envelope | `success=true` |
| Secrets | Não expostos |
| PII | Não exposta |
| Contrato | `schema_version=1.0.0` |
| Required endpoints | Declarados em `/api/runtime/contracts` |

## Limites

Este incremento não substitui autenticação, observabilidade interna, métricas protegidas, dashboard operacional ou validações E2E de login.

## Próxima evolução

Criar página pública ou interna `/runtime` consumindo esses contratos para exibir health cards, build info, dependencies e drill-down operacional.
