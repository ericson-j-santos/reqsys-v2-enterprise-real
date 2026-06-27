# Projeção Estatística de Conclusão — ReqSys

## Objetivo

Fornecer projeção governada de conclusão do ecossistema ReqSys, separando explicitamente:

| Conceito | Regra |
|---|---|
| Estado evidenciado | Somente o que existe no código, testes e artifacts |
| Estado alvo | Meta estratégica declarada |
| Projeção | Resultado esperado mantendo ritmo observado |

Referência ADR-022: projeção **nunca** pode ser promovida a evidenciado sem validação completa.

## Referência temporal

Baseline governado: **27/06/2026 21:00 BRT** (`2026-06-27T21:00:00-03:00`).

## Superfícies

| Superfície | Caminho |
|---|---|
| API | `GET /v1/estatisticas/projecao-conclusao` |
| Artifact CI | `artifacts/completion-projection/completion-projection.json` |
| Script | `scripts/completion_projection_engine.py` |
| Schema | `docs/contracts/completion-projection.schema.json` |
| UI | Aba Projeção em `/estatisticas` |

## Estrutura do snapshot

- `estado_atual_consolidado` — dimensões com percentual e maturidade
- `velocidade_observada` — cadência de PRs, merges, CI e lead time
- `percentual_conclusao_real` — indicadores com tipo `evidenciado` ou `projeção`
- `gaps_restantes` — gap percentual por área
- `projecao_tempo` — marcos conservador e acelerado (dias úteis)
- `gargalos_principais` — limitantes atuais ordenados
- `indice_risco` — riscos estatísticos
- `tendencias` — direção por indicador
- `probabilidades_finais` — probabilidade por resultado
- `aceleradores_marginais` — maior ganho marginal atual
- `leitura_executiva` — síntese para stakeholders

## Fórmulas e regras

### Média de dimensões

```
media_dimensoes = sum(status_percentual) / count(dimensoes)
```

### Gap médio

```
gap_medio = sum(gap_percentual) / count(gaps)
```

### Confiança

- Baseline inicial: **87%** (cadência observada estável, regressão crítica baixa)
- Projeção dinâmica futura exige amostra mínima de **30 ciclos** (padrão predictive stability layer)

### Cenários de tempo

| Cenário | Premissa |
|---|---|
| Conservador | Ritmo atual sem aceleração estrutural |
| Acelerado (recomendado) | Incrementos paralelos, CI auto-remediável, validação contínua |

Estimativas em **dias úteis**, não calendário.

## Guard rails

1. Todo indicador de projeção deve ter `tipo` explícito.
2. UI deve rotular projeção visualmente (chip `projeção`).
3. `confianca_percentual` abaixo de 60 bloqueia cenário acelerado como recomendado.
4. Artifact CI é `report_only` — não altera gates nem deploy.
5. Enriquecimento dinâmico permitido apenas para `requisitos_concluidos` via banco operacional.

## Próximos incrementos

1. Histórico versionado de snapshots para regressão.
2. Integração com `ci-lead-time-analytics.json`.
3. Projeção dinâmica por sprint (Agile Runtime `sprintMetrics`).
4. Drill-down por gap → backlog acionável.
