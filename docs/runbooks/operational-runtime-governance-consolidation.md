# Operational Runtime Governance Consolidation

Versão: `0.1.0`  
Data de referência: `2026-06-29`  
Modo operacional: `assistido`, `auditável`, `read-only por padrão`

## Objetivo

Consolidar os incrementos de maior retorno estatístico do ReqSys em uma frente única, com foco Pareto:

1. estabilidade de CI/CD e recuperação assistida;
2. evidência operacional consolidada;
3. observabilidade runtime P1;
4. governança de contratos;
5. camada Power Platform Runtime.

O objetivo não é criar novas features horizontais, mas reduzir o maior gargalo atual: retrabalho operacional, PRs amarelos, evidência fragmentada e validação manual recorrente.

## Escopo implementado neste incremento

| Frente | Entrega | Estado |
|---|---|---|
| CI Recovery | Política objetiva para rerun, fix e substituição limpa de PR | Definida |
| Governance Hub | Índice JSON canônico para consolidação operacional | Definido |
| Observability P1 | Critérios mínimos de correlação, logs e evidência | Definidos |
| Contract Governance | Gate de drift e versionamento semântico | Definido |
| Power Platform Runtime | Runbook de runtime bridge e ALM assistido | Definido |

## Decisão arquitetural

A consolidação deve consumir artefatos existentes, especialmente:

- `scripts/pr_auto_recovery.py`;
- `docs/ops-dashboard/data/health.json`;
- `docs/ops-dashboard/data/openapi-governance-index.json`;
- `docs/contracts/artifact-contracts-index.md`;
- `artifacts/observability-correlation-report/observability-correlation-report.json`.

Não deve criar painéis paralelos quando já houver fonte canônica. O padrão recomendado é adicionar índices e contratos leves que apontem para as evidências existentes.

## Política Pareto de execução

### P0 — Primeiro corrigir estabilidade

Critérios:

- workflow crítico falhando;
- PR não mergeável;
- Evidence Gate ausente;
- contrato OpenAPI ou artifact contract sem evidência;
- ambiente sem health check rastreável.

Ação padrão:

1. diagnosticar pelo script read-only;
2. classificar severidade;
3. corrigir menor superfície possível;
4. validar CI;
5. só então publicar link operacional.

### P1 — Depois consolidar evidência

Critérios:

- evidência existe, mas está dispersa;
- dashboard não agrega semáforo por ambiente;
- histórico executivo não permite burndown.

Ação padrão:

1. publicar JSON canônico;
2. adicionar runbook de consumo;
3. versionar schema;
4. evitar acoplamento ao frontend até o dado estabilizar.

### P2 — Por fim ampliar integração

Critérios:

- runtime estável;
- contratos versionados;
- ambiente DEV evidenciado;
- fluxo Power Platform sem dependência de credenciais no Git.

Ação padrão:

1. criar bridge mockada;
2. validar OpenAPI;
3. versionar coleção/post payload;
4. só depois automatizar provisionamento real.

## Quality gates obrigatórios

| Gate | Critério mínimo |
|---|---|
| Segurança | Nenhum secret, token, tenant secret ou JWT real versionado |
| CI | Workflow deve operar em modo read-only ou validação local |
| Governança | Toda fonte precisa de owner, status e path rastreável |
| Observabilidade | Todo runtime event deve carregar `correlation_id` |
| Contratos | Mudança de contrato exige schema/versionamento |
| Power Platform | Provisionamento real exige aprovação humana e ambiente segregado |

## Métricas esperadas

| Métrica | Alvo inicial |
|---|---:|
| Taxa de PRs verdes após primeira correção | >= 80% |
| Evidências operacionais consolidadas | >= 90% |
| Gaps críticos sem owner | 0 |
| Ambientes com health rastreável | 100% |
| Contratos com versão explícita | 100% |

## Próximo incremento natural

Implementar o consumo visual do arquivo:

- `docs/ops-dashboard/data/operational-runtime-governance-consolidation.json`

no Ops Dashboard, com cards por frente Pareto e semáforo operacional.