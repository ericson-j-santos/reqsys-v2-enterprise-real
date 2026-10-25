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
- R13: um segundo PC previamente registrado pode receber o perfil base por uma label bootstrap de capacidade aprovada, sem comparar hostname nem aceitar `runner_id` como entrada.
- R14: o onboarding remoto do segundo PC deve produzir evidência antes de agendar uma única reinicialização do listener, e a label compartilhada só pode ser reconciliada depois que o runner voltar online.
- R15: monitoramento e reconciliação hospedados devem usar tokens efêmeros da GitHub App governada, com permissões mínimas de administração, sem PAT pessoal ou credencial vinculada a um PC.
- R16: o onboarding PC24x7 que exige privilégios deve reutilizar somente a tarefa local preexistente `ReqSysDesktopAdminBroker` com S4U, nível máximo e trigger de inicialização; o job não recebe segredo administrativo, não solicita UAC e o broker revalida comentário owner exato, SHA, checkout limpo, raiz do runner, escopo DEV e perfil `base` antes de agendar uma única reinicialização.
- R17: o job Windows PowerShell 5.1 existente de CI deve executar o instalador com `runner_root` inexistente e `-LabelConfirmation`, comprovar bloqueio por pré-requisito sem conflito de binding ou saída zero e confirmar ausência de criação de diretório ou mutação do host.
- R18: o perfil `runtime` do PC `pc24x7` usa o manifesto fixo `%LOCALAPPDATA%\ReqSys\runner-pool.json`; quando esse arquivo existe, os preflights `base` e `runtime` devem preferi-lo ao caminho legado da variável, aceitar capacidade configurada cumulativamente superior, recusar reparse points em toda a cadeia, não alterar `.env` ou serviço e registrar que reinício não é necessário.
- R19: onboarding e jobs do perfil `runtime` devem exigir registro válido do runner atual, Docker CLI e Docker Engine respondendo exclusivamente por named pipe Windows local allowlisted, além de runtime root DEV válido; a reconciliação hospedada deve selecionar e confirmar exatamente um runner online e ocioso.
- R20: a reconciliação deve falhar fechado até a instalação da GitHub App governada possuir `Administration: Read and write` e `Actions: Read-only`; não é permitido reintroduzir PAT ou degradar a ausência dessa permissão para sucesso.
- R21: os dispatches físicos e de reconciliação do perfil `runtime` devem aceitar somente o owner ou `github-actions[bot]`, sempre combinados com comentário owner exato, SHA atual e janela temporal; colaborador não pode reutilizar um comentário visível para dispatch direto.
