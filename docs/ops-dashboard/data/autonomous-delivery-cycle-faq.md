# FAQ — Autonomous Delivery Cycle

## Ele mergeia sozinho qualquer PR verde?

Não. Só processa PR com `cycle:auto-merge-approved` e `merge-queue:eligible`.

## Ele corrige CI vermelho?

Não. CI vermelho bloqueia o ciclo.

## Ele executa o próximo incremento automaticamente?

Não. O próximo incremento é capturado em fila report-only para ser validado no chat/agente.

## O que acontece se não houver PR candidato?

Publica relatório vazio, sem erro.

## O que acontece se o CI pós-merge falhar?

O relatório marca atenção requerida e o próximo incremento deve ser bloqueado até correção.
