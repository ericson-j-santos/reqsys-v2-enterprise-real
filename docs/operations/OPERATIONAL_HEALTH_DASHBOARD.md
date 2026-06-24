# ReqSys Operational Health Dashboard

## Objetivo

Consolidar uma camada governada para acompanhar a saúde operacional do repositório ReqSys durante ciclos acelerados de entrega.

## Escopo

Este incremento define o modelo de dashboard para:

- PR aging;
- conflict risk;
- stale branch index;
- CI health trend;
- merge readiness score;
- classificação operacional de PRs.

## Classificação operacional

| Classe | Critério | Decisão |
|---|---|---|
| `production-ready` | PR pequeno, fora de draft, CI verde, mergeable=true | Pode seguir para merge controlado |
| `governance-only` | Documentação, gates, runbooks ou evidências sem alteração runtime | Pode seguir com validação leve |
| `experimental` | Draft, PoC, spike ou branch de investigação | Não entra no caminho crítico |
| `blocked` | CI falha, conflito, branch defasada ou risco alto | Recriar/atualizar antes de merge |
| `superseded` | Escopo já absorvido por main ou PR posterior | Fechar administrativamente |

## Merge readiness score

Score base: `100`.

Reduções recomendadas:

| Condição | Penalidade |
|---|---:|
| Draft | -25 |
| CI diferente de verde | -30 |
| Não mergeável | -35 |
| Branch atrás da main | até -20 |
| PR com mais de 7 dias | -10 |
| PR com mais de 14 dias | -20 |

Critério recomendado:

- `>= 85`: apto para merge controlado;
- `70–84`: revisar antes de merge;
- `< 70`: bloquear e corrigir;
- branch antiga com alto drift: recriar limpa a partir da main.

## Stale branch governance

Uma branch deve ser tratada como obsoleta quando ocorrer qualquer condição:

- PR draft antigo sem atividade relevante;
- branch mais de 5 commits atrás da main;
- escopo já absorvido por outro PR;
- PR duplicado com mesmo objetivo;
- PR não mergeável após consolidação da main.

Decisão padrão:

1. fechar PR superseded/duplicado;
2. registrar justificativa no corpo do PR;
3. recriar em branch limpa se ainda for necessário;
4. evitar resolver conflitos acumulados quando o escopo for pequeno.

## Health dashboard mínimo

| Indicador | Estado alvo |
|---|---|
| CI principal | Verde |
| PR Conflict Guard | Verde |
| PR CI Watch | Verde |
| Governance Quality Gates | Verde |
| Branch Protection Audit | Verde |
| PR Evidence Gate | Verde |
| Drafts antigos | Zerados ou classificados |
| Superseded abertos | Zerados |
| PRs production-ready | Score >= 85 |

## Guardrails

Este incremento:

- não executa deploy;
- não altera produção;
- não altera permissões;
- não altera configurações sensíveis;
- não executa merge automático;
- apenas versiona governança operacional.

## Próxima evolução

Evoluir este modelo para um gerador automático que publique artifacts JSON/Markdown/HTML a partir dos PRs abertos e runs recentes do GitHub Actions.
