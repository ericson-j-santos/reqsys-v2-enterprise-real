# Perfil nativo DEV sem Docker — contrato de admissão somente leitura (#3138)

## Objetivo
Criar a capacidade ausente de identificação e validação de um perfil DEV nativo **separado** do perfil Docker existente, sem aplicar label, fazer dispatch, manipular segredo ou substituir as rotas e workflows existentes.

## Requisitos
1. O novo perfil `native_runtime` usa label exclusiva `reqsys-dev-native-runtime-v1`, **nunca** o label `reqsys-dev-runtime-v1` do perfil Docker. O contrato é estático, sem executar host, Azure, Docker ou qualquer serviço externo.
2. O contrato exige Windows x64, Git, Python, Node, repositório ReqSys e DEV; toda lista de labels, ferramentas, ambiente e comandos proibidos é de equivalência exata.
3. Um manifesto/configuração, label de runner ou sucesso de CI **não** certificam `ready_for_work`; o validador estático retorna `false` e `dispatch_allowed=false`.
4. Para verificar um recibo, exigir emissão por processo independente, autenticada com HMAC-SHA256 de chave de verificação independente, vinculada a SHA integral, identidade do runner/host físico, lease, checkpoint, origem, perfil, momento recente e gates positivos.
5. Rejeitar recibo adulterado, assinatura inválida, campo extra, host não correspondente, SHA diferente, PROD/HML, Docker como perfil, runner busy/offline, dependência nativa ausente, lease/checkpoint inválido, custo não comprovado, replay diferente, carimbo expirado/futuro ou ausência de chave de verificação.
6. A saída de um recibo válido pode afirmar `signed_receipt_validated`, mas **não autoriza** despacho nem certifica continuidade física da mesma tarefa entre dois hosts. A emissão física de recibos ainda exige Session Launcher, Gateway e Validator real.
7. Manter perfil Docker legado, workflows, labels e credenciais intactos; nenhuma ativação do novo perfil nesta mudança.
8. Custo incremental máximo R$ 0,00. Nenhuma transação administrativa, migração de job, produção ou deploy.

## Critérios de aceite (Acceptance Criteria)
1. Config JSON válida, com perfil `native_runtime` exclusivo e sem Docker em ferramentas permitidas.
2. Teste positivo de configuração retorna `ready_for_work=false` e `dispatch_allowed=false`.
3. Teste positivo de recibo **sintético em teste** assinado sob chave descartável retorna `signed_receipt_validated`, sem dispatch nem continuidade certificada; não equivale a E2E físico.
4. Negativos de chave/assinatura, SHA, ambiente, perfil, runner, idade e os sete gates falham fechado.
5. Replay da mesma entrada do verificador é determinístico e não modifica labels, manifestos, arquivos ou hosts.
6. O teste automatizado `tests/test_reqsys_native_dev_profile.py` passa no SHA exato, em execução isolada, com pelo menos uma mutação negativa do próprio teste.
7. Pre-PR Ready e CI/Validator independentes no novo SHA, PR rascunho única por `idempotency_key`; não marcar `READY_FOR_WORK` ou `E2E_PASS` com CI verde.
8. Uma etapa futura e separada deve integrar este contrato ao preflight e ao onboarding governados, obter recibo físico contemporâneo e certificar dois hosts; até lá `ADOPTION_PENDING` e `BLOCKED_PHYSICAL_CROSS_HOST_E2E`.
