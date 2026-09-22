# Runtime-Aware Merge Queue

Atualizado em: 2026-06-27

## Objetivo

Definir o próximo incremento governado para transformar a merge queue em uma fila sensível ao estado real de runtime, reduzindo merges verdes no CI que ainda possam degradar o ambiente público.

## Escopo do incremento

Este incremento adiciona o contrato operacional para a fila de merge governada por runtime. A implementação deve continuar pequena, rastreável e compatível com PRs paralelos.

### Entradas obrigatórias

- Resultado dos checks do PR.
- Smoke runtime pós-build.
- Sinal de health do runtime validator.
- Estado de incidentes abertos.
- Matriz de conflito por lane.
- Evidência de contratos preservados.

### Estados da fila

| Estado | Critério | Ação |
|---|---|---|
| `waiting_ci` | Checks ainda em execução | Manter PR fora da janela de merge |
| `waiting_runtime_smoke` | CI verde, smoke pendente | Bloquear auto-merge |
| `eligible` | CI verde + smoke verde + sem incidente crítico | Liberar para auto-merge governado |
| `paused_by_incident` | Incidente crítico ou runtime degradado | Pausar merges da lane impactada |
| `requires_rebase` | Base defasada ou risco de conflito | Atualizar branch antes de merge |
| `blocked_by_contract` | Contrato strict alterado sem evidência | Bloquear até validação explícita |

## Política Pareto

1. Não aumentar escopo funcional dentro da fila.
2. Não misturar refactor transversal com feature.
3. Não promover PR sem evidência de runtime.
4. Não liberar auto-merge em estado degradado.
5. Preferir PRs pequenos por lane independente.

## Fluxo alvo

```text
PR aberto
  -> validação isolada
  -> classificação de lane
  -> CI obrigatório
  -> smoke runtime
  -> checagem de incidentes
  -> elegibilidade na merge queue
  -> auto-merge governado
  -> evidência pós-merge
```

## Critérios de aceite

- Existe contrato claro de estados da merge queue.
- O PR pode ser validado sem depender de mudanças em código produtivo.
- O artefato permite implementação posterior de automação sem conflito estrutural.
- A fila diferencia CI verde de runtime realmente seguro.

## Próximo incremento técnico

Criar script `scripts/runtime_merge_queue_gate.py` para gerar saída JSON com:

```json
{
  "eligible": true,
  "state": "eligible",
  "lane": "runtime-governance",
  "blocking_reasons": [],
  "evidence": {
    "ci": "green",
    "runtime_smoke": "green",
    "incidents": "none-critical"
  }
}
```
