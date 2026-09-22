# RSM-07 — CHANGE Traceability + Change Evidence Loop — Requisitos

Issue: #1789

## Requisito 1 — referências canônicas
Um `ServiceCase(type=CHANGE)` deve referenciar requisito, SDD e PR por identificadores externos, sem duplicar os dados canônicos dessas fontes.

## Requisito 2 — SHA completo e exato
O contexto de rastreabilidade deve registrar o SHA completo do head validado. SHA abreviado deve ser rejeitado e comparação por prefixo não é permitida.

## Requisito 3 — CI vinculado ao mesmo SHA
A evidência de CI deve registrar `run_id`, `head_sha` e `conclusion`. Somente `conclusion=success` do mesmo SHA exato da rastreabilidade pode ser aceita.

## Requisito 4 — execução real vinculada ao SHA
A evidência de execução deve persistir referência de deploy/runtime, ambiente, `runtime_sha`, instante observado, URI e digest SHA-256 da evidência pós-deploy. `runtime_sha` deve ser exatamente igual ao `head_sha` do CHANGE.

## Requisito 5 — fechamento fail-closed
`ServiceCase(type=CHANGE)` pode alcançar `RESOLVED` antes da validação pós-deploy, mas a transição `RESOLVED -> CLOSED` deve falhar fechado enquanto não existir evidência runtime persistida e satisfatória para o mesmo SHA.

## Requisito 6 — falha e rollback
Evidência pós-deploy com status `FAILED` deve manter o fechamento bloqueado. O fechamento após falha só pode ocorrer com status `ROLLED_BACK` e referência, runtime SHA e evidência de rollback completos. O SHA observado após rollback deve ser completo e diferente do SHA revertido.

## Requisito 7 — idempotência e histórico
O registro de evidência deve ser idempotente por `event_id`, preservar histórico append-only em `rsm_service_case_events` e rejeitar reutilização do mesmo `event_id` para efeito divergente.

## Requisito 8 — sem efeito implícito de produção
O ciclo de evidência não executa merge, deploy, promoção ou rollback. Ele registra e valida evidência produzida por executores autorizados. Produção continua sujeita aos gates e autorizações existentes.

## Critérios de aceite
1. CHANGE com requisito, SDD, PR, CI `success`, deploy/runtime e pós-deploy no mesmo SHA é aceito.
2. Runtime SHA divergente do SHA do CHANGE é rejeitado sem persistência.
3. Fechamento sem evidência runtime é rejeitado e preserva `RESOLVED`.
4. Evidência `FAILED` mantém o fechamento bloqueado.
5. Evidência `ROLLED_BACK` só é válida com rollback completo e SHA de runtime pós-rollback diferente do SHA revertido.
6. Replay do mesmo `event_id` converge sem duplicar evidência nem evento.
7. `REQUEST`, `INCIDENT` e `PROBLEM` não aceitam o contrato de evidência de CHANGE.
8. E2E executa API HTTP real + PostgreSQL real, confirma `build_sha == expected_sha`, prova o bloqueio sem evidência, registra evidência válida, fecha o CHANGE e confirma o efeito por leitura SQL independente.
9. Controle negativo com runtime SHA divergente falha e não deixa efeito persistido.
10. Nenhuma ação de produção é executada por este incremento.
