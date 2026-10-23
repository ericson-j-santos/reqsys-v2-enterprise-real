# Requisitos — pool compartilhado de runners ReqSys DEV

- R1: workflows DEV portáveis não podem selecionar um hostname ou `runner_id` fixo.
- R2: elegibilidade deve ser expressa por labels compartilhadas e manifesto local versionado por esquema.
- R3: o preflight deve falhar fechado para OS, ferramentas, capacidade, origem Git, runtime root, identidade DEV e salvaguardas.
- R4: runtime root e evidência devem ser independentes do hostname.
- R5: HML, STG, PROD e retry automático devem permanecer desabilitados.
- R6: onboarding e retirada de PCs devem ser documentados e automatizados sem registrar ou reconfigurar o serviço automaticamente.
- R7: testes devem impedir a reintrodução de `DESKTOP-PDQK954` ou `runner_id` fixo nos workflows portáveis.
- R8: esta evolução não executa dispatch, retry, deploy ou mutação de ambiente.
