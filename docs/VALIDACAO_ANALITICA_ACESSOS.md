# Validação analítica de acessos — ReqSys v2 Enterprise Real

## Objetivo

Consolidar as URLs públicas conhecidas da solução, os critérios de validação operacional e o modelo analítico mínimo para acompanhar disponibilidade, status HTTP e tempo de resposta.

## URLs de acesso

| Ambiente | Aplicação | API / Health | Finalidade |
| --- | --- | --- | --- |
| Produção | `https://reqsys-app.fly.dev/` | `https://reqsys-api.fly.dev/health` | Uso principal da solução |
| Staging / interno | `https://reqsys-app-stg.fly.dev/` | `https://reqsys-api-stg.fly.dev/health` | Homologação e validação controlada |
| Desenvolvimento | `https://reqsys-app-dev.fly.dev/` | `https://reqsys-api-dev.fly.dev/health` | Testes técnicos e validação incremental |
| Produção local Docker | `http://localhost:8081` | `http://localhost:8081/api/docs` | Execução local com compose de produção |
| Desenvolvimento local Docker | `http://localhost:8083` | `http://localhost:8211/docs` | Execução local de desenvolvimento |
| Testes E2E local Docker | `http://localhost:8084` | `http://localhost:8212/docs` | Execução local dedicada para testes |

## Validação automatizada

Script criado:

```bash
npm run validate:access
```

Arquivo:

```text
scripts/validar-acessos-publicos.mjs
```

Workflow:

```text
.github/workflows/validacao-acessos.yml
```

## Gatilhos do workflow

| Gatilho | Quando executa | Comportamento esperado |
| --- | --- | --- |
| `workflow_dispatch` | Execução manual pela UI ou GitHub CLI | Permite escolher `fail_on_unavailable=true` ou `false` |
| `push` em `main` | Após merge ou push direto na branch principal | Executa validação bloqueante com `fail_on_unavailable=true` |
| `schedule` | Diariamente às 10:17 UTC | Executa validação recorrente com `fail_on_unavailable=true` |

## Governança do workflow

- Permissão mínima declarada: `contents: read`.
- Concorrência controlada por branch via `validacao-acessos-${{ github.ref }}`.
- Execuções novas cancelam execuções anteriores ainda em andamento para a mesma referência.
- O relatório analítico é publicado sempre que o job executa, inclusive em falha controlada.
- O artefato publicado é `validacao-acessos-publicos.json`.

## Campos analíticos gerados

O relatório JSON contém:

| Campo | Descrição |
| --- | --- |
| `generatedAt` | Data/hora UTC da execução |
| `timeoutMs` | Timeout aplicado por chamada |
| `analytics.total` | Total de URLs avaliadas |
| `analytics.reachable` | Quantidade de URLs alcançadas |
| `analytics.expected` | Quantidade com status HTTP esperado |
| `analytics.unavailable` | Quantidade indisponível |
| `analytics.unexpectedStatus` | Quantidade com status inesperado |
| `analytics.reachablePercent` | Percentual de disponibilidade técnica |
| `analytics.expectedPercent` | Percentual de conformidade por status |
| `analytics.avgDurationMs` | Tempo médio de resposta das URLs alcançadas |
| `analytics.maxDurationMs` | Maior tempo de resposta observado |
| `analytics.byEnvironment` | Quebra por ambiente: produção, staging e desenvolvimento |
| `results[]` | Evidência por URL validada |

## Critérios de aceite operacionais

| Critério | Regra |
| --- | --- |
| API Health | Deve retornar `200` |
| Aplicação Web | Pode retornar `200`, `301`, `302`, `401` ou `403`, desde que esteja alcançável |
| Timeout | Cada URL deve responder dentro de `ACCESS_VALIDATION_TIMEOUT_MS` |
| Falha controlada | `ACCESS_VALIDATION_FAIL_ON_UNAVAILABLE=false` permite relatório sem quebrar a pipeline manual |
| Falha bloqueante | `ACCESS_VALIDATION_FAIL_ON_UNAVAILABLE=true` falha a execução em indisponibilidade/status inesperado |
| Pós-merge | Todo `push` na `main` deve gerar relatório de validação pública |

## Observação da validação externa neste ambiente

A tentativa de validação direta a partir do ambiente desta sessão não conseguiu resolver os domínios públicos `fly.dev`. Por isso, a validação definitiva foi materializada como workflow GitHub Actions, que deve executar em ambiente com rede pública funcional e publicar o relatório como artefato.

## Interpretação recomendada

| Cenário | Decisão recomendada |
| --- | --- |
| `reachablePercent = 100` e `expectedPercent = 100` | Acesso público íntegro |
| `reachablePercent = 100` e `expectedPercent < 100` | Ambiente responde, mas há divergência de status HTTP |
| `reachablePercent < 100` | Investigar DNS, deploy, healthcheck, Fly.io, TLS ou roteamento |
| `avgDurationMs` crescente por vários dias | Investigar latência, cold start, plano gratuito, recursos ou dependências externas |
| Produção falha e dev/staging passam | Priorizar rollback ou verificação de secrets/variáveis de produção |
| Dev falha e produção passa | Bloquear promoção de novas mudanças até estabilizar ambiente técnico |

## Próximo incremento recomendado

Persistir o JSON de validação em um histórico versionado ou storage externo para gerar tendência temporal de disponibilidade e latência por ambiente.
