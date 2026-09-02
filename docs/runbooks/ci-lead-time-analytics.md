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
- Pareto de falhas por workflow;
- gargalos por P95;
- baseline histórico do incidente de 143 minutos.

## Artefatos publicados

- `audit/ci-lead-time-analytics.json`
- `audit/ci-lead-time-analytics.md`

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
| Evolução | trend comparison | Delta entre janela recente e anterior |

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

## Critérios iniciais

| Indicador | Alvo inicial |
|---|---:|
| Success rate | >= 95% |
| Failure rate | <= 5% |
| First-pass success | >= 90% |
| P95 lead time | < 15 minutos |
| Max lead time recorrente | < 60 minutos |
| Evidência publicada | 100% das execuções agendadas |

CV, fila, rerun rate e throughput começam como baseline observacional. Limites de gate só devem ser definidos depois de histórico suficiente.

## Validação

O workflow executa antes da coleta:

```bash
python tests/scripts/test_build_ci_process_improvement_analytics.py
```

A suíte cobre percentis, primeira passagem, reexecução, variabilidade, fila, throughput, tendência e Pareto.

## Próximo incremento

Persistir séries temporais dessas métricas no histórico operacional e apresentar no Command Center o delta por período sem promover qualquer novo limite a gate até existir baseline estável.
