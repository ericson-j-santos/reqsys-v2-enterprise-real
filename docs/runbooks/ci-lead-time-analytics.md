# CI Lead Time Analytics

## Objetivo

Medir melhoria de processo no CI/CD do ReqSys com evidência periódica, separando velocidade, qualidade, previsibilidade, fila, capacidade e concentração de falhas.

O mecanismo continua `report-only`: não substitui nem relaxa gates obrigatórios.

## Escopo

O workflow `CI Lead Time Analytics` coleta as execuções recentes do GitHub Actions e publica:

- quantidade de runs analisadas e concluídas;
- taxa de sucesso e falha;
- sucesso na primeira tentativa (`first_pass_success_rate_percent`);
- taxa de reexecução (`rerun_rate_percent`);
- lead time médio, P50, P90, P95 e máximo;
- desvio-padrão e coeficiente de variação;
- tempo médio e P95 de fila;
- throughput por hora e por dia na janela observada;
- comparação entre metade mais recente e metade anterior da janela;
- comparação da janela atual com o baseline congelado de 2026-09-02;
- Pareto de falhas por workflow;
- gargalos por P95;
- baseline histórico do incidente de 143 minutos.

## Artefatos publicados

- `audit/ci-lead-time-analytics.json`
- `audit/ci-lead-time-analytics.md`

A partir do contrato `1.0.3`, o JSON recebe `baseline_comparison` antes do upload.

## Dimensões de melhoria

| Dimensão | Indicadores principais | Interpretação |
|---|---|---|
| Tempo | P50, P90, P95, máximo | Velocidade e cauda do processo |
| Qualidade | success/failure rate | Estabilidade funcional |
| Primeira passagem | first-pass success, rerun rate | Retrabalho operacional |
| Previsibilidade | desvio-padrão, CV | Dispersão e consistência |
| Fluxo | avg/P95 queue | Espera antes da execução |
| Capacidade | throughput | Volume processado por unidade de tempo |
| Priorização | failure Pareto | Poucos workflows que concentram falhas |
| Evolução interna | trend comparison | Delta entre janela recente e anterior |
| Evolução histórica | baseline comparison | Delta da janela atual contra a referência congelada |

## Comparação com baseline congelado

Referência imutável:

`audit/baselines/ci-process-improvement-baseline-2026-09-02.json`

A cada execução, `scripts/compare_ci_process_baseline.py` compara a janela atual com essa referência em três grupos:

| Grupo | Deltas |
|---|---|
| Qualidade | success rate, failure rate, first-pass success, rerun rate |
| Velocidade | média, P50, P95, P95 de fila |
| Variabilidade | desvio-padrão e coeficiente de variação |

Cada métrica recebe um sinal `improved`, `stable` ou `regressed`. O conjunto recebe `overall_signal` (`improved`, `stable`, `regressed` ou `mixed`).

Esses sinais são descritivos. `baseline_comparison.creates_gate` permanece `false` e `mode` permanece `report-only`.

Se o baseline não puder ser carregado, o artifact continua sendo publicado com `baseline_comparison.available=false`; ausência de comparação não derruba a geração da evidência. Alterar o baseline para `frozen=false` ou mudar sua identidade histórica é coberto por teste de regressão.

## Política operacional

O workflow é `report-only`.

Ele não substitui nem relaxa:

- `CI — ReqSys v2 Enterprise`;
- `Governance Quality Gates`;
- `Governança Padrão Ouro`.

Nenhum novo KPI deve ser usado isoladamente como prova causal. Correlação e tendência indicam onde investigar; causa raiz continua exigindo evidência técnica.

## Regras de interpretação

- P95 menor com CV menor indica processo simultaneamente mais rápido e previsível.
- P95 menor com CV maior indica ganho de velocidade com aumento de instabilidade.
- `first_pass_success_rate_percent` baixo indica retrabalho mesmo quando o success rate final parece saudável.
- `p95_queue_seconds` alto com execução estável indica gargalo de capacidade/fila, não necessariamente no workflow.
- Pareto deve orientar a primeira investigação, não eliminar análise de severidade.
- Throughput só deve ser comparado entre janelas de tamanho e comportamento semelhantes.
- A comparação de tendência usa duas metades cronológicas da mesma janela.
- A comparação histórica sempre usa o mesmo baseline congelado; o relógio e a referência não variam entre execuções.

## Critérios iniciais

| Indicador | Alvo inicial |
|---|---:|
| Success rate | >= 95% |
| Failure rate | <= 5% |
| First-pass success | >= 90% |
| P95 lead time | < 15 minutos |
| Max lead time recorrente | < 60 minutos |
| Evidência publicada | 100% das execuções agendadas |

CV, fila, rerun rate e throughput continuam como baseline observacional. Os deltas contra o baseline também não criam limite de gate.

## Validação

O workflow executa antes da coleta:

```bash
python tests/scripts/test_build_ci_process_improvement_analytics.py
python tests/scripts/test_compare_ci_process_baseline.py
```

A primeira suíte cobre percentis, primeira passagem, reexecução, variabilidade, fila, throughput, tendência e Pareto. A segunda cobre agrupamento dos deltas, modo `report-only`, ausência segura de baseline, rejeição de baseline mutável, idempotência e identidade da referência congelada.

## Próximo incremento

Persistir uma série histórica dos `baseline_comparison.delta` e apresentá-la no Command Center para observar tendência por período sem promover qualquer delta a gate até existir amostra temporal suficiente e critério estatístico formal.
