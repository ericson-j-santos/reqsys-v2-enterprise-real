# Contrato de KPIs — CI Lead Time Analytics

## Objetivo

Formalizar o contrato do artifact `ci-lead-time-analytics.json` para consumo por dashboards, evidências operacionais, burndown executivo e validações automatizadas.

## Artifact governado

- Nome lógico: `ci-lead-time-analytics.json`
- Schema: `docs/contracts/ci-lead-time-analytics.schema.json`
- Schema version gerada: `1.0.3`
- Modo: `report-only`
- Fonte: GitHub Actions API + baseline congelado versionado
- Permissões: `actions: read` e `contents: read`

A versão `1.0.3` é aditiva: preserva os campos de `1.0.2` e acrescenta `baseline_comparison` depois da coleta, antes do upload do artifact.

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
| `baseline_comparison` | objeto | Janela atual contra baseline congelado |
| `failure_pareto` | lista | Concentração de falhas |
| `bottlenecks` | lista | Top workflows por P95 |

## Semântica

### Primeira passagem

Uma execução conta como primeira passagem quando `conclusion == success` e `run_attempt == 1`. A taxa usa como denominador todas as execuções concluídas da janela.

### Fila

`queue_seconds = run_started_at - created_at`.

`execution_seconds = updated_at - run_started_at`.

`duration_seconds = updated_at - created_at`.

Valores negativos são normalizados para zero.

### Variabilidade

- desvio-padrão: população observada na janela;
- coeficiente de variação: `stddev / mean * 100`.

### Tendência interna

As execuções concluídas são ordenadas por `created_at`. A metade mais recente é comparada com a metade anterior por success rate, failure rate, P50, P95 e CV.

### Comparação histórica congelada

A referência é `audit/baselines/ci-process-improvement-baseline-2026-09-02.json`.

`baseline_comparison.delta` possui três grupos:

- `quality`: success rate, failure rate, first-pass success e rerun rate;
- `speed`: média, P50, P95 e P95 de fila;
- `variability`: desvio-padrão e CV.

Cada indicador recebe `improved`, `stable` ou `regressed`. `overall_signal` pode ser `improved`, `stable`, `regressed` ou `mixed`.

Regras fixas de governança:

- `baseline_comparison.mode == report-only`;
- `baseline_comparison.creates_gate == false`;
- deltas são evidência descritiva e não prova causal;
- baseline ausente ou ilegível resulta em `available=false`, sem impedir publicação da evidência;
- baseline marcado como mutável (`frozen != true`) é rejeitado pelo comparador e coberto por teste.

### Pareto

Falhas são agrupadas por workflow, ordenadas por contagem decrescente e recebem participação e participação acumulada.

## Classificação executiva

| Condição | Efeito |
|---|---|
| P95 >= 900 s | warning |
| Max >= 3600 s | warning |
| Failure rate > 5% | warning |
| First-pass success < 90% | warning |
| Demais casos | passed |

A comparação com baseline não altera essa classificação e não cria gate.

## Governança

- Não registrar token, secret ou conteúdo sensível.
- URLs de workflow são permitidas apenas para rastreabilidade.
- CV, fila, throughput e deltas históricos permanecem observacionais.
- Nenhum delta deve virar gate sem série temporal suficiente e critério estatístico formal.
- Mudança incompatível deve elevar a versão do contrato.

## Testes

```bash
python tests/scripts/test_build_ci_process_improvement_analytics.py
python tests/scripts/test_compare_ci_process_baseline.py
```

Critério mínimo: ambas as suítes totalmente verdes antes da geração e enriquecimento do artifact.
