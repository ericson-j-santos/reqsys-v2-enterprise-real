# Public Runtime Evidence Gate

## Objetivo

Criar uma evidência operacional recorrente e acionável da disponibilidade pública do ReqSys, sem executar deploy, sem alterar secrets e sem depender de aprovação humana.

Este gate complementa o runtime Fly P0 já versionado e transforma a URL pública em sinal objetivo para o Estado Único ReqSys.

## Escopo

O workflow `.github/workflows/public-runtime-evidence.yml` executa validação read-only contra a API pública e publica artifact com:

- `public-runtime-validation.json`;
- `public-runtime-summary.md`.

## Endpoints mínimos validados

Por padrão, o workflow reaproveita `scripts/validate_public_runtime.py` e valida:

```text
GET /
GET /health
GET /api/runtime/health
GET /api/runtime/readiness
GET /api/runtime/liveness
GET /api/runtime/metrics
GET /api/runtime/dashboard
```

## Execução manual

```bash
gh workflow run "Public Runtime Evidence Gate" \
  -f public_url="https://reqsys-api.fly.dev" \
  -f strict=true
```

## Execução recorrente

O workflow roda a cada 6 horas por `schedule` para produzir sinal operacional contínuo.

## Critério de sucesso

| Critério | Estado esperado |
|---|---|
| Workflow | `success` |
| Artifact | `public-runtime-evidence` publicado |
| `success_percentual` | `100.0` |
| Endpoints mínimos | Todos HTTP 2xx |
| Secrets | Nenhum valor exposto |
| Deploy | Não executado |

## Modo strict

Com `strict=true`, qualquer endpoint público com erro faz o workflow falhar.

Com `strict=false`, o artifact ainda é publicado para diagnóstico sem travar o workflow.

## Uso no Estado Único ReqSys

Este gate alimenta diretamente:

- deploy/URL pública;
- evidências críticas;
- progresso de produção;
- confiança operacional;
- risco operacional;
- decisão de consolidar ou não produção.

## Limites

Este gate não:

- cria app Fly;
- aplica secrets;
- executa deploy;
- corrige DNS;
- altera autenticação;
- substitui validação E2E de login Microsoft.

## Próxima evolução recomendada

Após estabilização deste gate, adicionar publicação do resumo em comentário automático de PR/release ou painel operacional interno do ReqSys.
