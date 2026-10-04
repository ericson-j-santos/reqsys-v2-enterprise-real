# REQSYS-OPER-006 — Monitoramento estratégico das pendências

## Objetivo

Reconciliar o incremento histórico do PR #61 com a arquitetura atual do monitoramento operacional, sem regredir as capacidades de observabilidade, coleta dinâmica e correlação adicionadas posteriormente à `main`.

## Requisitos

1. O contrato deve usar `schema_version = 1.2.0`.
2. `modo_coleta` e `coleta_detalhes` atuais devem ser preservados.
3. Itens devem suportar `proximo_passo` e `criterio_de_fechamento`.
4. O resumo deve expor `frentes_criticas` e `itens_prontos_para_merge`, calculados a partir da lista real de itens.
5. O snapshot deve expor `tempo_operacional` com estimativas positivas e coerentes com o estado geral.
6. A lógica deve permanecer no schema/serviço atual; a API de observabilidade não deve ser substituída pela implementação histórica do PR.
7. Correlação atual por `X-Correlation-ID`/`X-Request-ID` deve permanecer intacta.
8. Nenhum campo de tempo pode ser tratado como evidência de conclusão, CI ou runtime.
9. Testes devem validar os valores dos agregados, e não apenas a existência dos campos.
10. Nenhum merge, deploy ou promoção de ambiente é realizado pelo incremento de reconciliação.

## Critérios de aceite

- Testes direcionados de monitoramento operacional verdes no HEAD atual.
- Ruff/segurança e SDD verdes.
- Branch com `behind_by=0` e mergeável.
- Nenhuma regressão nos endpoints de runtime/observabilidade existentes.
