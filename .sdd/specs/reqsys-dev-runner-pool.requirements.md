# Requisitos — pool compartilhado de runners ReqSys DEV

## Critérios de aceite

- R1: workflows DEV portáveis não podem selecionar um hostname ou `runner_id` fixo.
- R2: elegibilidade deve ser expressa por labels compartilhadas e manifesto local versionado por esquema.
- R3: o preflight deve falhar fechado para OS, ferramentas, capacidade, origem Git, runtime root, identidade DEV e salvaguardas.
- R4: runtime root e evidência devem ser independentes do hostname.
- R5: HML, STG, PROD e retry automático devem permanecer desabilitados.
- R6: onboarding e retirada de PCs devem ser documentados e automatizados sem registrar ou reconfigurar o serviço automaticamente.
- R7: testes devem impedir a reintrodução de `DESKTOP-PDQK954` ou `runner_id` fixo nos workflows portáveis.
- R8: esta evolução não executa dispatch, retry, deploy ou mutação de ambiente.
- R9: o scheduler deve exigir uma label compatível com o perfil `base`, `runtime` ou `ollama` antes do pickup.
- R10: o onboarding em Windows PowerShell 5.1 deve gravar JSON em UTF-8 sem BOM.
- R11: uma automação local fixa pode configurar a `.env` e reiniciar somente um serviço `actions.runner.*` explicitamente informado, sem aceitar comandos arbitrários.
- R12: a aplicação de labels pelo instalador deve exigir confirmação literal, usar o `agentId` registrado localmente, preservar labels não gerenciadas e reconciliar as labels do pool com o conjunto validado do perfil.
