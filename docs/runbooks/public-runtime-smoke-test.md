# Public Runtime Smoke Test

## Objetivo

Evitar falso negativo de publicação pública quando a raiz `/` retorna `not found` mesmo com a API saudável.

## Endpoints públicos mínimos

```bash
curl -i https://reqsys-api.fly.dev/
curl -i https://reqsys-api.fly.dev/health
curl -i https://reqsys-api.fly.dev/api/runtime/health
curl -i https://reqsys-api.fly.dev/api/runtime/readiness
curl -i https://reqsys-api.fly.dev/api/runtime/liveness
curl -i https://reqsys-api.fly.dev/api/runtime/metrics
```

## Critério de sucesso

- `/` deve retornar JSON com links operacionais.
- `/health` deve retornar status `ok`.
- `/api/runtime/*` deve retornar HTTP 200 após deploy do backend atualizado.
- `/api/runtime/metrics` deve retornar `text/plain`.

## Diagnóstico rápido

| Sintoma | Interpretação |
|---|---|
| `Could not resolve host` | problema DNS/conectividade do cliente |
| `/` retorna `not found` | rota raiz ausente ou deploy antigo |
| `/health` retorna 200 e runtime retorna 404 | deploy anterior ao Runtime Operational Observability v1 |
| todos retornam 404 | app Fly errado, proxy errado ou backend não publicado |

## Guardrails

- Sem secrets.
- Sem PII.
- Sem relaxamento de gates.
- Sem alteração de CORS.
- Sem ação destrutiva.
