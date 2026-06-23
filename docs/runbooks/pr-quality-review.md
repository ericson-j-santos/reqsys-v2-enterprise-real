# PR Quality Review

## Objetivo

Substituir a dependência operacional do CodeRabbit por uma revisão determinística executada em GitHub Actions.

## Componentes

- Workflow: `.github/workflows/pr-quality-review.yml`
- Script: `scripts/pr_quality_review.py`
- ADR: `docs/adr/ADR-0024-substituicao-coderabbit-pr-quality-review.md`

## Política

| Severidade | Comportamento |
|---|---|
| `critical` | Falha o workflow |
| `warning` | Registra evidência sem bloquear por padrão |
| `ok` | Sem bloqueio objetivo |

## Evidências

O workflow publica o artifact `pr-quality-review-report` contendo JSON e Markdown com métricas, achados, arquivos alterados e decisão operacional.
