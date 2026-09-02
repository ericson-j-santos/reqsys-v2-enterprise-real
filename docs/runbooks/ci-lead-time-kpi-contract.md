# Contrato de KPIs — CI Lead Time Analytics

## Objetivo

Formalizar o contrato do artifact `ci-lead-time-analytics.json` para consumo por dashboards, evidências operacionais, burndown executivo e validações automatizadas.

## Artifact governado

- Nome lógico: `ci-lead-time-analytics.json`
- Schema: `docs/contracts/ci-lead-time-analytics.schema.json`
- Schema version gerada: `1.0.2`
- Modo: `report-only`
- Fonte: GitHub Actions API
- Permissões: `actions: read` e `contents: read`

A versão `1.0.2` é aditiva: preserva os campos obrigatórios existentes e acrescenta indicadores de melhoria de processo.

## KPIs

| KPI | Tipo | Uso operacional |
|---|---|---|
| `success_rate_percent` | percentual | Saúde geral do CI |
| `failure_rate_percent` | percentual | Instabilidade observada |
| `first_pass_success_rate_percent` | percentual | Sucesso sem reexecução |
| `rerun_rate_percent` | percentual | Retrabalho operacional |
| `avg_seconds` | segundos | Lead time médio |
| `p50_seconds` | segundos | Mediana |
| `p90_seconds` | segundos | Cauda intermediária |
| `p95_seconds` | segundos | Cauda crítica recorrente |
| `max_seconds` | segundos | Pior caso observado |
| `stddev_seconds` | segundos | Dispersão absoluta |
| `cv_percent` | percentual | Variabilidade relativa |
| `avg_queue_seconds` | segundos | Espera média antes de iniciar |
| `p95_queue_seconds` | segundos | Cauda da fila |
| `throughput.runs_per_hour` | runs/hora | Capacidade observada |
| `trend_comparison` | objeto | Antes/depois dentro da janela |
| `failure_pareto` | lista | Concentração de falhas |
| `bottlenecks` | lista | Top workflows por P95 |

## Semântica

### Primeira passagem

Uma execução conta como primeira passagem quando:

- `conclusion == success`; e
- `run_attempt == 1`.

A taxa usa como denominador todas as execuções concluídas da janela. Assim, reexecuções bem-sucedidas continuam visíveis como retrabalho.

### Fila

`queue_seconds = run_started_at - created_at`.

`execution_seconds = updated_at - run_started_at`.

`duration_seconds = updated_at - created_at`.

Valores negativos são normalizados para zero para proteção contra inconsistência de timestamp.

### Variabilidade

- desvio-padrão: população observada na janela;
- coeficiente de variação: `stddev / mean * 100`.

CV igual a zero é usado quando não há dados suficientes ou a média é zero.

### Tendência

As execuções concluídas são ordenadas por `created_at`. A metade mais recente é comparada com a metade anterior usando:

- success rate;
- failure rate;
- P50;
- P95;
- CV.

A tendência é evidência descritiva, não prova causal.

### Pareto

Falhas são agrupadas por workflow, ordenadas por contagem decrescente e recebem participação e participação acumulada. O objetivo é priorizar investigação das causas que concentram maior volume de falhas.

## Classificação executiva

| Condição | Efeito |
|---|---|
| P95 >= 900 s | warning |
| Max >= 3600 s | warning |
| Failure rate > 5% | warning |
| First-pass success < 90% | warning |
| Demais casos | passed |

O status continua `report-only`.

## Governança

- Não registrar token, secret ou conteúdo sensível.
- URLs de workflow são permitidas apenas para rastreabilidade.
- Novos KPIs permanecem observacionais até existir baseline histórico.
- Nenhum limite de CV, fila ou throughput deve virar gate sem amostra suficiente.
- Mudança incompatível deve elevar a versão do contrato.

## Testes

```bash
python tests/scripts/test_build_ci_process_improvement_analytics.py
```

Critério mínimo: suíte totalmente verde antes de gerar o artifact.
