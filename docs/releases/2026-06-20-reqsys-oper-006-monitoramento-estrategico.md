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

## Reconciliação operacional — 2026-10-04

- Alterações funcionais foram portadas para a arquitetura atual de `schemas` + `services/monitoramento_snapshot.py`, sem sobrescrever a API de observabilidade evoluída na `main`.
- O contrato 1.2.0 preserva `modo_coleta` e `coleta_detalhes` e acrescenta próximos passos, critérios de fechamento, agregados derivados e tempo operacional.
- O teste de resumo valida valores reais derivados dos itens, evitando falso verde por mera existência de campos.
- A branch é sincronizada com a `main` no commit de recuperação e volta a ser validada pelos gates atuais no novo HEAD.

Refs #30 #31 #32 #33 #46
