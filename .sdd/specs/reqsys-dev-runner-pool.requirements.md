# Requisitos — pool compartilhado de runners ReqSys DEV

## Critérios de aceite

- R1: workflows DEV portáteis não podem selecionar um hostname ou `runner_id` fixo.
- R2: elegibilidade deve ser expressa por labels compartilhadas e manifesto local versionado por esquema.
- R3: o preflight deve falhar fechado para OS, ferramentas, capacidade, origem Git, runtime root, identidade DEV e salvaguardas.
- R4: runtime root e evidência devem ser independentes do hostname.
- R5: HML, STG, PROD e retry automático devem permanecer desabilitados.
- R6: onboarding e retirada de PCs devem ser documentados e automatizados sem registrar ou reconfigurar o serviço automaticamente.
- R7: testes devem impedir a reintrodução de `DESKTOP-PDQK954` ou `runner_id` fixo nos workflows portáteis.
- R8: esta evolução não executa dispatch, retry, deploy ou mutação de ambiente.
- R9: a confirmação explícita para reconciliar labels deve usar parâmetro dedicado, sem colidir com o parâmetro comum `-Confirm` de `SupportsShouldProcess`.
