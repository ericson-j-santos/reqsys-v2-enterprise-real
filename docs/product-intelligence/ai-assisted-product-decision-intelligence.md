# AI-assisted Product Decision Intelligence

## Objetivo

Gerar recomendação assistida e governada para decisão funcional do ReqSys a partir de sinais de qualidade, rastreabilidade, risco e prontidão.

## Capacidades implementadas

- Gerador determinístico sem chamada externa de IA.
- Decisão assistida baseada em regras governadas.
- Consolidação de score funcional.
- Consolidação de grafo de rastreabilidade.
- Consolidação de dashboard funcional.
- Racional da recomendação.
- Próximas ações objetivas.
- Relatórios JSON, Markdown e HTML.
- Workflow CI dedicado.
- Artifact de decisão funcional.

## Decisões possíveis

| Decisão | Uso |
|---|---|
| PROCEED_TO_GOVERNED_IMPLEMENTATION | Requisito com qualidade e rastreabilidade suficientes |
| REFINE_BEFORE_IMPLEMENTATION | Requisito parcial que precisa de refinamento |
| BLOCK_AND_REFINE | Requisito abaixo do mínimo seguro |

## Governança

- Não executa agentes automaticamente.
- Não chama provedor externo de IA.
- Não altera runtime produtivo.
- Mantém revisão humana obrigatória quando necessário.
- Mantém PII mascarada conforme evento de origem.
- Mantém rastreabilidade por correlation_id.

## Limites

- Não substitui aprovação humana.
- Não cria implementação automaticamente.
- Não abre PRs de produto automaticamente.
- Não integra bases corporativas reais.
- Não altera gates operacionais existentes.

## Próximo incremento recomendado

ReqSys Product Intelligence Living Backlog.
