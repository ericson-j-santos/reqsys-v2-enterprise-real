# Merge Readiness Pareto Gate

## Objetivo

Reduzir o retrabalho causado por PRs impossíveis de mergear, branches atrasadas, PRs grandes demais e alterações acopladas em muitos domínios.

## Problema atacado pelo Pareto

O histórico operacional recente indicou concentração de falhas em poucos gargalos:

1. branch divergente;
2. CI/deploy acoplado ao merge;
3. PR grande demais;
4. muitos workflows alterados no mesmo incremento;
5. evidências externas travando fluxo de engenharia.

Este gate atua antes de pipelines pesados para evitar desperdício de CI e reduzir o lead time.

## Validações

O workflow `.github/workflows/merge-readiness.yml` executa `scripts/merge_readiness_gate.py` e valida:

| Critério | Regra |
|---|---|
| Branch atrasada | bloqueia se `behind_by > 0` |
| Conflito de merge | bloqueia se o dry-run de merge falhar |
| Tamanho do PR | bloqueia se passar de 25 arquivos |
| Workflows alterados | bloqueia se passar de 3 arquivos em `.github/workflows/` |
| Domínios misturados | alerta se passar de 4 domínios |

## Evidência

O gate publica:

```text
artifacts/merge-readiness/merge-readiness.json
```

Campos principais:

```json
{
  "status": "ready|blocked",
  "ahead_by": 0,
  "behind_by": 0,
  "changed_files": 0,
  "workflow_files": 0,
  "domains": [],
  "blocking_issues": [],
  "warnings": []
}
```

## Decisão operacional

Este gate deve ser obrigatório antes de CI/deploy pesado. Deploy público, smoke externo e evidências operacionais não devem ser pré-condição direta para validar mergeability estrutural.

## Próximo incremento recomendado

Adicionar agregação histórica dos resultados em `docs/ops-dashboard/data/merge-readiness-history.json` para medir:

- percentual de PRs bloqueados por divergência;
- média de arquivos por PR;
- domínios mais misturados;
- tendência de redução de retrabalho.
