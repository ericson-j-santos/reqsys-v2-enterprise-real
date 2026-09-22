# RSM-07 — CHANGE Traceability — Requisitos

Issue: #1789

## Requisito 1 — referências canônicas
Um `ServiceCase(type=CHANGE)` deve referenciar requisito, SDD e PR por identificadores externos, sem duplicar os dados canônicos dessas fontes.

## Requisito 2 — SHA completo e exato
O contexto de rastreabilidade deve registrar o SHA completo do head validado. SHA abreviado deve ser rejeitado e comparação por prefixo não é permitida.

## Requisito 3 — CI vinculado ao mesmo SHA
A evidência de CI deve registrar `run_id`, `head_sha` e `conclusion`. Somente `conclusion=success` do mesmo SHA exato da rastreabilidade pode ser aceita.

## Requisito 4 — fail-closed sem efeito implícito
Evidência ausente, falha ou pertencente a outro SHA deve bloquear a validação sem alterar o estado do `ServiceCase`. O contrato não executa merge, deploy ou rollback.

## Fora de escopo deste incremento
- persistência e API do RSM-02;
- política completa de aprovação do RSM-04;
- consulta à API do GitHub;
- deploy/runtime real;
- evidência pós-deploy;
- execução de rollback/reversão.

Esses elementos deverão compor o mesmo vínculo por SHA em incrementos posteriores, sem enfraquecer a igualdade exata.

## Critérios de aceite
1. CHANGE com requisito, SDD, PR e CI `success` no SHA exato é aceito pelo harness.
2. CI verde pertencente a outro SHA é rejeitado.
3. Evidência de CI ausente é rejeitada.
4. O contrato não pode ser aplicado a `REQUEST`, `INCIDENT` ou `PROBLEM`.
5. SHA abreviado é rejeitado.
6. Casos rejeitados preservam o estado original.
7. `backend/tests/test_service_management_domain.py` passa no HEAD exato.
