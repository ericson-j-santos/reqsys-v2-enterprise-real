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
- R10: o onboarding físico não deve receber secrets administrativos; a reconciliação remota da label deve ocorrer somente depois da evidência sanitizada do perfil local.
- R11: a reconciliação remota deve ocorrer em runner hospedado, exigir autorização owner e SHA atual, consumir uma evidência de onboarding bem-sucedida cujo contrato local permaneça inalterado, resolver exatamente um runner por labels e validar readback sem `runner_id` fixo.
- R12: o workflow hospedado de reconciliação deve constar tanto da rota owner quanto da allowlist fixa de dispatch, com teste de regressão que impeça divergência entre as duas listas.
