# Runtime Evidence Analytics

## Objetivo

Criar uma camada inicial de analytics operacional para evidências públicas do runtime ReqSys.

Este incremento adiciona endpoints e página navegável para histórico, resumo e tendência, mantendo o contrato strict público inalterado.

## Endpoints

```text
GET /api/runtime/evidence/history
GET /api/runtime/evidence/summary
GET /api/runtime/evidence/trends
GET /runtime/evidence
```

## Escopo v1

A versão inicial usa baseline operacional em memória para expor contrato e UX sem depender de storage externo.

## Campos principais

| Campo | Uso |
|---|---|
| `availability_percentual` | Percentual strict do último snapshot |
| `confidence_score` | Confiança operacional consolidada |
| `required_ok` / `required_total` | Gate strict público |
| `trend` | Tendência de estabilidade |
| `risk` | Risco operacional simplificado |

## Limites

- Não persiste snapshots reais ainda.
- Não consulta artifacts históricos do GitHub ainda.
- Não calcula MTTR real ainda.
- Não substitui observabilidade interna.

## Próxima evolução

Integrar os artifacts `public-runtime-evidence` do GitHub Actions como fonte histórica real para disponibilidade rolling, latência, incident timeline e scorecard executivo.
