# Conflict Prediction Contract

Atualizado em: 2026-06-27

## Objetivo

Definir o contrato inicial para um mecanismo de predição de conflito antes do merge, combinando paths alterados, lanes, contratos públicos, histórico de PRs e risco arquitetural.

## Problema que resolve

Conflitos aparecem tarde quando vários PRs evoluem em paralelo sem uma camada comum de classificação. O objetivo é detectar risco antes do merge, sem bloquear indevidamente incrementos seguros.

## Escopo deste incremento

Este PR cria apenas o contrato de predição. A implementação executável deve vir em incremento posterior, em arquivo novo e com saída JSON.

## Sinais avaliados

| Sinal | Peso inicial | Descrição |
|---|---:|---|
| `changed_paths_overlap` | Alto | Dois ou mais PRs alteram o mesmo arquivo ou diretório crítico |
| `public_contract_change` | Alto | API, schema, rota, evento ou contrato strict alterado |
| `runtime_surface_change` | Alto | Alteração em deploy, health, worker, observabilidade ou boot |
| `frontend_route_change` | Médio | Alteração em navegação, layout global ou rotas |
| `docs_only` | Baixo | Arquivo documental isolado |
| `artifact_only` | Baixo | Artefato operacional estático e novo |
| `test_only` | Baixo/Médio | Teste isolado ou atualização ampla de suíte |

## Níveis de risco

| Risco | Critério | Ação recomendada |
|---|---|---|
| `low` | Arquivo novo, docs/artifact, sem contrato público | Pode seguir em paralelo |
| `medium` | Toca código isolado ou testes compartilhados | Requer CI verde e revisão de lane |
| `high` | Toca runtime, main, router, deploy ou contrato público | Requer smoke + merge queue governada |
| `blocked` | Sobreposição crítica com PR aberto ou contrato quebrado | Pausar até resolver base/conflito |

## Saída JSON alvo

```json
{
  "risk": "low",
  "lane": "runtime-governance",
  "parallel_safe": true,
  "blocking_reasons": [],
  "signals": {
    "changed_paths_overlap": false,
    "public_contract_change": false,
    "runtime_surface_change": false,
    "docs_only": true
  }
}
```

## Critérios de aceite

- Existe taxonomia clara para risco de conflito.
- O contrato diferencia conflito textual, semântico e operacional.
- O modelo permite aumento de PRs paralelos sem comprometer mergeability.
- O próximo incremento executável pode ser implementado sem alterar runtime produtivo.

## Próximo incremento técnico

Criar `scripts/conflict_prediction_gate.py` para receber lista de arquivos alterados e produzir a classificação JSON acima. O primeiro modo deve ser deterministic-only, sem IA, para manter reprodutibilidade em CI.
