# Golden Release Operational Checklist — ReqSys

## Objetivo

Definir checklist operacional padrão ouro para liberar uma rodada de incrementos após merges na `main`, mantendo segurança, evidência, rastreabilidade e baixo risco.

## Checklist pre-release

| Item | Critério | Obrigatório |
|---|---|---|
| PRs da rodada | Até 3 PRs paralelos por rodada padrão | Sim |
| CI obrigatório | Required workflows verdes | Sim |
| Trilha D (padrão ouro) | Seis dimensões paralelas verdes | Sim |
| Conflitos | Sem conflito com `main` | Sim |
| Escopo | Sem ampliação não planejada | Sim |
| Secrets | Sem novo secret ou vazamento | Sim |
| Deploy/runtime | Sem alteração inesperada | Sim |
| Artifacts | Publicados quando aplicável | Sim |
| Schemas | Validados quando aplicável | Sim |
| Dashboard | Atualizado quando consumir novo artifact | Condicional |
| Runbook | Atualizado para novo workflow/artifact | Condicional |

## Checklist pos-merge

| Item | Evidência esperada |
|---|---|
| Main Operational Post-Merge Health | Artifact JSON/MD publicado |
| CI Lead Time Analytics | P50/P95 atualizados |
| Runtime Predictive Analytics | Risk score atualizado |
| Operational Artifact Schema Validation | Contratos mínimos validados |
| Trilha D — Qualidade e Governança | Artifact `trilha-d-qualidade-governanca-evidence` com `gold_standard: true` |
| Dashboard dinâmico | Fontes e fallback funcionais |
| Burndown/maturidade | Gap residual atualizado |

## Ordem de merge recomendada

1. Contracts e schemas.
2. Workflows report-only.
3. Dashboard/visualização.
4. Backend/runtime.
5. Produção/deploy somente após evidência.

## Semáforo executivo

| Condição | Decisão |
|---|---|
| CI obrigatório verde e report-only com warning não crítico | Pode seguir |
| CI obrigatório verde e artifact ausente por falta de execução recente | Pode seguir com observação |
| CI obrigatório falhou | Não seguir |
| Alteração de secrets/deploy não planejada | Não seguir |
| Conflito com `main` | Rebase/corrigir antes |

## Métricas da rodada

Registrar sempre:

- quantidade de PRs;
- taxa de merge;
- taxa de CI verde;
- linhas adicionadas/removidas;
- arquivos alterados;
- lead time médio;
- riscos encontrados;
- correções pós-merge.

## Política fixa

A rodada padrão do ReqSys deve manter até 3 PRs paralelos. Até 5 PRs só é aceitável quando todos forem docs, contratos ou artifacts novos e independentes.
