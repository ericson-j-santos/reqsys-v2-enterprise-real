# Prompt — Executor do ciclo autônomo governado no chat

Use este prompt no chat/agente quando quiser consumir a fila de próximos incrementos capturada pelo `Autonomous Delivery Cycle`.

```text
@GitHub

Consuma o arquivo:
- docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json

Objetivo:
- validar se existe fila de próximos incrementos;
- priorizar somente itens com status queued_for_chat_execution;
- verificar o estado atual de PRs, CI e main antes de qualquer ação;
- executar apenas o próximo incremento seguro, pequeno, governado e sem conflito;
- abrir PR separado;
- aguardar CI verde antes de sugerir merge;
- não declarar concluído sem evidência.

Regras obrigatórias:
- não executar incremento se main estiver vermelho;
- não executar incremento se houver PR crítico pendente;
- não duplicar item já implementado;
- preservar contratos públicos e artifacts existentes;
- manter alteração pequena e rastreável;
- registrar evidência e changelog quando aplicável;
- retornar links clicáveis somente quando houver CI verde ou ação executável real.
```

## Uso recomendado

Após merge verde e fila preenchida, execute o prompt acima para continuar o ciclo sem perder contexto.
