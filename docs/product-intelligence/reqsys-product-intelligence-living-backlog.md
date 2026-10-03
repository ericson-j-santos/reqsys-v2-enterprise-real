# ReqSys Product Intelligence Living Backlog

## Objetivo

Gerar backlog funcional vivo a partir dos artifacts da camada `ReqSys Product Intelligence Layer`, sem escrita automática em sistemas externos.

## Capacidades implementadas

- Gerador Python sem dependências externas.
- Geração determinística de itens candidatos de backlog.
- Priorização P0/P1/P2 baseada em qualidade, rastreabilidade e decisão assistida.
- Consolidação de qualidade funcional.
- Consolidação de rastreabilidade funcional.
- Consolidação de decisão assistida.
- Relatórios JSON, Markdown e HTML.
- Workflow CI dedicado.
- Artifact de backlog funcional vivo.

## Itens candidatos iniciais

| Tipo | Objetivo |
|---|---|
| quality_refinement | Refinar qualidade funcional do requisito |
| traceability_completion | Completar rastreabilidade funcional |
| decision_review | Revisar decisão funcional assistida |

## Regras iniciais de prioridade

| Prioridade | Critério |
|---|---|
| P0 | Bloqueio/refinamento crítico, score < 40 ou rastreabilidade < 20 |
| P1 | Refinamento antes de implementação, score < 75 ou rastreabilidade < 60 |
| P2 | Requisito pronto para implementação governada |

## Governança

- Não escreve em GitHub Issues automaticamente.
- Não escreve em Redmine automaticamente.
- Não executa agentes automaticamente.
- Mantém revisão humana obrigatória.
- Mantém PII mascarada conforme evento de origem.
- Mantém rastreabilidade por correlation_id.

## Limites

- Não altera runtime produtivo.
- Não adiciona dependências externas.
- Não integra bases corporativas reais.
- Não substitui priorização humana.
- Não altera gates operacionais existentes.

## Próximo incremento recomendado

Product Intelligence Backlog Publisher Governado.
