# Histórico da homologação Workflow Efficiency

## Objetivo

Acumular evidências da homologação do artifact `ops-dashboard-static` e disponibilizar tendência executiva antes de qualquer promoção para gate bloqueante.

## Indicadores

- quantidade de amostras;
- taxa de homologação;
- sequência estável consecutiva;
- tendência do score em pontos;
- elegibilidade para revisão de promoção.

## Política de elegibilidade

Apenas sinaliza `eligible_for_blocking_review=true` quando todos os critérios forem atendidos:

- pelo menos 30 amostras;
- taxa de homologação mínima de 98%;
- sequência estável mínima de 20 execuções.

A elegibilidade não altera automaticamente o gate. O domínio permanece com `report_only=true` e `production_blocker=false`.

## Retenção

O artifact `workflow-efficiency-homologation-history` mantém até 50 amostras e é retido por 90 dias.

## Promoção futura

A promoção para critério obrigatório exige PR separado, decisão explícita, rollback documentado e validação do histórico acumulado.
