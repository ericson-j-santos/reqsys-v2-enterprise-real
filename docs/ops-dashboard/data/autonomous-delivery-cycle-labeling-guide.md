# Guia de labels — Autonomous Delivery Cycle

## Labels necessárias

### `merge-queue:eligible`

Gerada/aplicada pela fila governada quando o PR passou por validação isolada e integração temporária.

### `cycle:auto-merge-approved`

Autorização explícita para o ciclo automático tentar merge quando tudo estiver verde.

## Ordem recomendada

1. Aguardar `merge-queue:eligible`.
2. Confirmar CI obrigatório verde.
3. Aplicar `cycle:auto-merge-approved`.
4. Deixar o workflow processar o PR.

## Remoção preventiva

Remover `cycle:auto-merge-approved` se qualquer check ficar vermelho, se houver conflito ou se o escopo aumentar.
