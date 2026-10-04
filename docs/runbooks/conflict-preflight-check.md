# Conflict Preflight Check

> Atualização: 2026-06-30 13:30 BRT  
> Escopo: runbook para validação prévia de conflitos entre PRs.

## Objetivo

Definir uma checagem objetiva antes de abrir ou continuar PRs paralelos no ReqSys, reduzindo retrabalho, branches obsoletas e conflitos evitáveis.

## Ordem de validação

1. Listar PRs abertos contra `main`.
2. Coletar arquivos alterados por PR.
3. Comparar interseção de caminhos.
4. Classificar risco por tipo de arquivo.
5. Bloquear empilhamento quando houver conflito em arquivos críticos.
6. Preferir novo PR apenas quando o escopo for independente.

## Classificação de risco por caminho

| Caminho | Risco | Critério |
| --- | --- | --- |
| `.github/workflows/**` | Alto | Pode afetar CI/CD global. |
| `backend/**` | Alto | Pode alterar contrato ou runtime Python. |
| `backend-dotnet/**` | Alto | Pode alterar API .NET e testes. |
| `frontend/src/**` | Médio/Alto | Pode afetar UX e rotas. |
| `docs/**` | Baixo/Médio | Baixo quando são arquivos novos isolados. |
| `docs/ops-dashboard/data/**` | Baixo/Médio | Baixo para arquivos novos; médio se índice compartilhado. |
| `CHANGELOG.md` | Médio/Alto | Alto quando múltiplos PRs abertos editam o topo. |

## Decisão recomendada

| Situação | Decisão |
| --- | --- |
| Sem arquivos sobrepostos | Pode abrir PR paralelo. |
| Sobreposição apenas documental não crítica | Avaliar merge sequencial. |
| Sobreposição em código executável | Não abrir PR paralelo; consolidar em uma branch. |
| Sobreposição em workflow | Bloquear paralelismo. |
| Branch atrás da `main` | Atualizar antes de continuar. |

## Saída esperada

```json
{
  "status": "green",
  "overlapping_files": [],
  "risk_level": "low",
  "recommendation": "parallel_pr_allowed"
}
```

## Rollback

Remover este runbook. Não há alteração em aplicação, CI, deploy, banco ou contratos públicos.
