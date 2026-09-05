# CI Lead Time Analytics

## Objetivo

Medir melhoria de processo no CI/CD do ReqSys com evidência periódica, separando velocidade, qualidade, previsibilidade, fila, capacidade, concentração de falhas e comparabilidade das amostras.

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
- avaliação estrutural de comparabilidade entre a amostra atual e o baseline;
- Pareto de falhas por workflow;
- gargalos por P95;
- baseline histórico do incidente de 143 minutos.

## Artefatos publicados

- `audit/ci-lead-time-analytics.json`
- `audit/ci-lead-time-analytics.md`
- `audit/history/ci-process-improvement-history.jsonl`

A partir do contrato `1.0.3`, o JSON recebe `baseline_comparison` antes do upload. O campo aditivo `window_comparability` é incluído sem alterar a versão do contrato e é permitido pelo contrato atual (`additionalProperties=true`).

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
| Comparabilidade | window comparability | Se o delta histórico foi observado em amostras estruturalmente semelhantes |

## Comparação com baseline congelado

Referência imutável:

`audit/baselines/ci-process-improvement-baseline-2026-09-02.json`

A cada execução, `scripts/compare_ci_process_baseline.py` compara a janela atual com essa referência em três grupos: qualidade, velocidade e variabilidade.

Cada métrica recebe um sinal `improved`, `stable` ou `regressed`. O conjunto recebe `overall_signal` (`improved`, `stable`, `regressed` ou `mixed`). Esses sinais são descritivos. `baseline_comparison.creates_gate` permanece `false` e `mode` permanece `report-only`.

## Comparabilidade estrutural da janela

`scripts/annotate_ci_window_comparability.py` é executado depois da comparação com o baseline e antes da persistência histórica.

A avaliação usa somente propriedades observáveis já existentes nas duas amostras:

- mesmo `window_runs` solicitado;
- razão entre `completed_runs` atual e baseline entre `0.80` e `1.25`;
- razão entre `window_span_hours` atual e baseline entre `0.80` e `1.25`.

Se qualquer condição falhar, `window_comparability.comparable_to_baseline=false` e `reason_codes` registra a causa. O resultado continua sendo publicado e não derruba a CI.

Essa regra representa **comparabilidade estrutural da amostra**. Ela não representa significância estatística, intervalo de confiança nem prova causal. O modo é `descriptive-only` e `creates_gate=false`.

O baseline congelado não é alterado. Seus dados históricos de amostra (`window_runs`, `completed_runs`, `window_span_hours`) são apenas lidos.

A informação de comparabilidade também é persistida em `audit/history/ci-process-improvement-history.jsonl`, cujo registro passa a `schema_version=1.0.1`. Registros antigos continuam válidos e são preservados sem migração destrutiva.

## Política operacional

O workflow é `report-only`.

Ele não substitui nem relaxa:

- `CI — ReqSys v2 Enterprise`;
- `Governance Quality Gates`;
- `Governança Padrão Ouro`.

Nenhum KPI deve ser usado isoladamente como prova causal. Correlação e tendência indicam onde investigar; causa raiz continua exigindo evidência técnica.

## Regras de interpretação

- P95 menor com CV menor indica processo simultaneamente mais rápido e previsível.
- P95 menor com CV maior indica ganho de velocidade com aumento de instabilidade.
- `first_pass_success_rate_percent` baixo indica retrabalho mesmo quando o success rate final parece saudável.
- `p95_queue_seconds` alto com execução estável indica gargalo de capacidade/fila, não necessariamente no workflow.
- Pareto deve orientar a primeira investigação, não eliminar análise de severidade.
- Throughput só deve ser comparado entre janelas de tamanho e comportamento semelhantes.
- `overall_signal` deve ser interpretado junto com `window_comparability`.
- `comparable_to_baseline=false` não invalida a medição; apenas impede tratá-la como comparação equivalente.
- A comparação de tendência usa duas metades cronológicas da mesma janela.
- A comparação histórica sempre usa o mesmo baseline congelado; a referência não varia entre execuções.

## Critérios iniciais

| Indicador | Alvo inicial |
|---|---:|
| Success rate | >= 95% |
| Failure rate | <= 5% |
| First-pass success | >= 90% |
| P95 lead time | < 15 minutos |
| Max lead time recorrente | < 60 minutos |
| Evidência publicada | 100% das execuções agendadas |

CV, fila, rerun rate, throughput, deltas e comparabilidade continuam observacionais. Nenhum deles cria limite de gate neste incremento.

## Validação

O workflow executa antes da coleta:

```bash
python tests/scripts/test_build_ci_process_improvement_analytics.py
python tests/scripts/test_compare_ci_process_baseline.py
python tests/scripts/test_annotate_ci_window_comparability.py
python tests/scripts/test_update_ci_process_history.py
python tests/scripts/test_restore_ci_process_history.py
python tests/scripts/test_enrich_command_center_ci_history.py
```

A suíte de comparabilidade cobre janela equivalente, diferença de tamanho efetivo, diferença de duração, metadados insuficientes, idempotência e preservação do contrato `1.0.3`.

## Próximo incremento

Após acumular medições com `window_comparability.comparable_to_baseline=true`, evoluir a sustentabilidade para considerar somente observações comparáveis e, apenas com amostra temporal suficiente, avaliar um critério estatístico formal. Nenhuma promoção automática a gate deve ocorrer antes dessa etapa.
