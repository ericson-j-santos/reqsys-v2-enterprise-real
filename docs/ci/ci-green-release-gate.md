# CI Green Release Gate

> Atualização: 2026-06-30 13:30 BRT  
> Escopo: critério operacional para considerar PR pronto sem alterar workflows.

## Objetivo

Formalizar o gate mínimo para liberar merge de PRs do ReqSys sem exigir validação manual repetitiva e sem expor links prematuros quando ainda houver falhas detectáveis.

## Decisão operacional

Um PR só deve ser tratado como pronto quando houver evidência de:

1. branch atualizada contra `main`;
2. ausência de conflito;
3. CI concluído com sucesso;
4. escopo compatível com o tipo de incremento;
5. rollback conhecido;
6. impacto funcional documentado.

## Estados

| Estado | Definição | Ação recomendada |
| --- | --- | --- |
| `ready_green` | CI verde, mergeável, sem conflito | Trazer link clicável e indicar pronto para merge. |
| `waiting_ci` | CI em execução ou pendente | Não solicitar validação manual; aguardar ou revalidar. |
| `needs_fix` | CI falhou ou conflito detectado | Abrir correção objetiva antes de novo incremento dependente. |
| `blocked` | Alteração crítica sem evidência mínima | Não mergear até evidência operacional. |

## Aplicação prática

- Links de PR devem ser priorizados quando o estado for `ready_green` ou quando houver ação executável clara.
- PRs com CI pendente não devem ser tratados como entrega consolidada.
- PRs com CI falho devem gerar correção objetiva em vez de novo empilhamento.
- PRs independentes podem continuar em paralelo desde que não alterem arquivos sobrepostos.

## Evidências mínimas

| Evidência | Fonte esperada |
| --- | --- |
| Mergeabilidade | Metadados do PR |
| CI | GitHub Actions |
| Escopo | Diff do PR |
| Rollback | Corpo do PR ou runbook |
| Impacto | Corpo do PR |

## Rollback

Remover este documento. Não há alteração em pipeline, aplicação, infraestrutura ou contrato público.
