# Operational Alert Intelligence

## Objetivo

Classificar alertas operacionais de CI/CD por criticidade, reduzir ruído e recomendar ações seguras.

## Capacidades implementadas

- Classificação de alertas por severidade.
- Separação entre sinal informativo, cancelamento e possível regressão.
- Política de ação operacional.
- Recomendação governada.
- Redução de ruído operacional.
- Artifacts em JSON, Markdown e HTML.

## Níveis de alerta

| Nível | Uso |
|---|---|
| INFO | Execução normal ou sinal informativo |
| MEDIUM | Cancelamento, contexto ambíguo ou execução substituída |
| HIGH | Falha com potencial regressão real |

## Políticas de ação

| Política | Significado |
|---|---|
| OBSERVE | Monitorar sem intervenção |
| VERIFY_CONTEXT | Verificar contexto antes de agir |
| MANUAL_REVIEW_REQUIRED | Revisão humana antes de qualquer remediação |

## Limites

- Não executa remediação automática.
- Não reexecuta workflows.
- Não altera runtime produtivo.
- Não remove nem flexibiliza gates.

## Próximo incremento

Unified Operational Event Bus.
