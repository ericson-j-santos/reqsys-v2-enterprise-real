# CI Lead Time Analytics

## Objetivo

Medir melhoria do processo de CI/CD do ReqSys com janelas temporais homogêneas. O mecanismo permanece `report-only`: mede e publica evidência, sem criar ou relaxar gates.

## Política de coleta horária

A partir deste incremento, a amostra principal deixa de depender dos últimos N workflows e passa a usar a política:

`fixed-60m-settle-5m-min30-v1`

| Regra | Valor |
|---|---:|
| Duração da janela | 60 minutos |
| Âncora UTC | minuto `:40` |
| Maturação antes da coleta | 5 minutos |
| Execuções concluídas mínimas | 30 |
| Cobertura mínima de conclusão | 90% |
| Paginação máxima da API | 20 × 100 runs |

O workflow continua agendado no minuto `:45`. Assim, uma execução normal às 15:45 mede exatamente `14:40–15:40`. Se o runner iniciar atrasado, por exemplo 15:58, a janela continua `14:40–15:40`; o atraso não desloca a amostra.

As janelas são definidas por `created_at` em intervalo fechado-aberto: `start_at <= created_at < end_at`.

## Elegibilidade da amostra

`collection_window.sample_eligible=true` somente quando todas as condições forem satisfeitas:

1. A paginação alcançou dados anteriores ao início da janela (`collection_complete=true`).
2. Existem pelo menos 30 execuções concluídas.
3. Pelo menos 90% das execuções criadas na janela já terminaram no momento da coleta.

Se alguma condição falhar, a medição é preservada no histórico como contexto, recebe `eligibility_reason_codes` e não participa da sustentabilidade.

A maturação de 5 minutos reduz o risco de contar como incompletos workflows criados imediatamente antes do fechamento da janela.

## Deduplicação

O workflow também pode rodar em `push` ou execução manual. Por isso, o histórico deduplica observações fixas por `collection_window.window_id`, formado por política + início + fim da janela. Duas execuções que medem a mesma hora representam uma única observação; a mais recente substitui a anterior.

## Métricas

Os cálculos existentes são preservados:

- sucesso e falha;
- sucesso na primeira tentativa e reexecução;
- média, P50, P90, P95 e máximo;
- desvio-padrão e coeficiente de variação;
- fila média e P95;
- throughput;
- Pareto de falhas;
- gargalos por workflow;
- tendência interna da amostra.

Na política horária, `throughput.window_span_hours=1.0` por definição, em vez de inferir a janela pela distância entre timestamps dos workflows observados.

## Baseline congelado de 02/09/2026

O arquivo `audit/baselines/ci-process-improvement-baseline-2026-09-02.json` permanece imutável.

Esse baseline foi coletado pelo método anterior, baseado em quantidade de runs. Portanto:

- continua disponível como referência histórica descritiva;
- `baseline_comparison` continua sendo produzido;
- `window_comparability` continua mostrando se a amostra atual seria estruturalmente equivalente ao baseline antigo;
- ele **não** é usado para decidir sustentabilidade das novas janelas horárias.

Nenhuma tentativa é feita de reclassificar artificialmente o baseline antigo como uma janela fixa de 60 minutos.

## Sustentabilidade

O Command Center passa a usar `homogeneous_fixed_time_windows`.

Somente janelas que sejam:

- `mode=fixed_time`;
- `sample_eligible=true`;
- `collection_complete=true`;
- da mesma `policy_id` ativa;

podem participar da decisão.

Cada janela é comparada à janela horária elegível imediatamente anterior em quatro dimensões:

- taxa de sucesso;
- taxa de falha;
- P95;
- coeficiente de variação (CV).

A transição é classificada como `improved`, `stable`, `regressed` ou `mixed`. São necessárias pelo menos **3 janelas horárias elegíveis** antes de sair de `insufficient_data`.

Critério observacional atual:

- `sustained_improvement`: pelo menos 60% das transições são melhoria e nenhuma é regressão;
- `regression_watch`: pelo menos 40% das transições são regressão;
- demais casos: `mixed`;
- menos de 3 janelas: `insufficient_data`.

Esse critério ainda não representa significância estatística nem prova causal e não cria gate.

## Artefatos

- `audit/ci-lead-time-analytics.json`
- `audit/ci-lead-time-analytics.md`
- `audit/history/ci-process-improvement-history.jsonl`
- `artifacts/workflow-command-center/ci-process-improvement-history.json`
- `artifacts/workflow-command-center/ci-process-improvement-history.md`

`collection_window` é um campo aditivo. O contrato final continua `1.0.3`, compatível com o schema atual que permite propriedades adicionais.

Novos registros do histórico usam `schema_version=1.0.2` e preservam registros antigos sem migração destrutiva.

## Governança

- Permissões do analytics permanecem `actions: read` e `contents: read`.
- Nenhum token ou segredo é persistido.
- `creates_gate=false` é preservado.
- O baseline congelado não é sobrescrito.
- Janelas inelegíveis permanecem visíveis como contexto, mas não influenciam sustentabilidade.
- Mudanças futuras de política devem alterar `policy_id`; políticas diferentes não são misturadas na mesma série de sustentabilidade.

## Validação

O workflow executa as suítes legadas e as novas suítes específicas:

```bash
python tests/scripts/test_build_ci_process_improvement_analytics.py
python tests/scripts/test_build_ci_fixed_window_analytics.py
python tests/scripts/test_compare_ci_process_baseline.py
python tests/scripts/test_annotate_ci_window_comparability.py
python tests/scripts/test_update_ci_process_history.py
python tests/scripts/test_update_ci_fixed_window_history.py
python tests/scripts/test_restore_ci_process_history.py
python tests/scripts/test_enrich_command_center_ci_history.py
python tests/scripts/test_ci_fixed_window_sustainability.py
```

Os testes novos cobrem: estabilidade da âncora temporal, maturação, filtro do cohort, quantidade mínima, cobertura mínima, paginação, persistência da política, deduplicação por janela, isolamento entre versões de política e classificação de sustentabilidade.

## Próximo critério de avanço

Depois de acumular pelo menos 3 janelas horárias elegíveis na `main`, o Command Center poderá sair de `insufficient_data`. Apenas após série temporal maior deve ser avaliado um critério estatístico formal, como mediana móvel, P95 móvel e limites de controle. Nenhuma promoção automática a gate faz parte deste incremento.
