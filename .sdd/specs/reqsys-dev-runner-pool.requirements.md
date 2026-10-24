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

- R9: scripts PowerShell com [CmdletBinding(SupportsShouldProcess)] não podem declarar parâmetro customizado Confirm, pois conflita com parâmetro comum automático; usar AuthorizationPhrase vinculada à literal de aceite de labels no workflow, validar parâmetro negativo e preservar WhatIf/Confirm nativos. Teste negativo em Windows deve executar apenas preflight com runner inexistente, sem alterar o ambiente.

- R10: o job Windows PowerShell 5.1 existente de CI deve executar o instalador com runner_root inexistente, verificar bloqueio por pré-requisito, rejeitar conflito de binding/saída zero e confirmar ausência de criação de diretório ou mutação. Não criar novo executor nem apagar o fluxo legado.
