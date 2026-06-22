# REQSYS-OPER-006 — Monitoramento estratégico das pendências abertas

## Contexto

Este incremento evolui o snapshot `/monitoramento-operacional` para rastrear pendências estratégicas abertas sem declará-las concluídas artificialmente.

## Entregue

- Contrato `schema_version = 1.2.0`.
- Campos por item: `proximo_passo` e `criterio_de_fechamento`.
- Campos no resumo: `frentes_criticas` e `itens_prontos_para_merge`.
- Bloco `tempo_operacional`.
- GovBI IA marcado como bloqueante até existir grounding, fonte válida e erro controlado.
- Dashboard para Analítico, Planner e Pipeline continuam como pendências rastreáveis.
- Testes de contrato atualizados para validar `schema_version = 1.2.0` e `tempo_operacional`.
- Documentação viva atualizada.

## Não entregue neste incremento

- Correção funcional final do GovBI IA.
- Drill-down universal completo.
- Integração Planner end-to-end real.
- Unificação total de pipeline e evidências HTML.

## Rebase operacional — 2026-06-22

- Branch limpa criada a partir da `main` atual.
- Alterações funcionais e documentais do PR #61 reaplicadas sobre a base atual.
- Objetivo: eliminar divergência operacional e permitir criação de merge ref para CI.
- PR deve permanecer em draft até CI verde no último head, revisão concluída e autorização explícita.

Refs #30 #31 #32 #33 #46
