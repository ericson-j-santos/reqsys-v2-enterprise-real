# Executive Predictive Stability Layer

## Objetivo

Criar uma camada executiva de estabilidade preditiva supervisionada para o ReqSys, usando o histórico persistente do GitHub Actions History Lake como fonte inicial.

## Fonte de dados

```text
data/operational/github-actions-history/runs.jsonl
```

## Capacidades implementadas

- Predictive stability scoring.
- Failure trend analysis.
- Workflow degradation detection.
- Duration volatility analysis.
- Confidence/risk supervision.
- Executive readiness state.
- Artifacts JSON, Markdown e HTML.

## Saídas

```text
artifacts/executive-predictive-stability/
├── executive-predictive-stability.json
├── executive-predictive-stability.html
└── summary.md
```

## Execução

```bash
python scripts/executive_predictive_stability_layer.py \
  --data-path data/operational/github-actions-history/runs.jsonl \
  --output-dir artifacts/executive-predictive-stability \
  --min-confidence 90 \
  --max-risk 10
```

## Indicadores críticos

| Indicador | Descrição |
|---|---|
| `predictive_precision_percent` | Precisão executiva estimada da entrega operacional |
| `confidence_percent` | Confiança estatística da leitura preditiva |
| `predicted_risk_percent` | Risco operacional previsto |
| `stability_score` | Score consolidado de estabilidade |
| `failure_trend_direction` | Tendência temporal de falha |
| `workflow_degradation_findings` | Workflows com indícios de degradação |

## Governança

- Sem deploy.
- Sem escrita externa.
- Sem alteração de secrets.
- Sem alteração de branch protection.
- Sem uso de IA externa.
- Revisão humana obrigatória.

## Limites atuais

A precisão estatística depende do volume de registros no History Lake. Com menos de 30 registros, o estado permanece `PREDICTIVE_STABILITY_WARMING_UP`. Com histórico mais longo, o modelo reduz penalidades e melhora confiança.

## Próximo incremento recomendado

Adicionar workflow governado de validação da camada preditiva, gerando artifacts em CI sem auto-commit e com permissões mínimas.
