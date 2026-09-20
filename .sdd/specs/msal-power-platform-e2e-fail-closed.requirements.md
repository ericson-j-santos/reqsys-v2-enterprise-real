# MSAL / Power Platform E2E fail-closed — Requisitos

## Objetivo

Impedir que o workflow de aceite real de conexões Power Platform finalize verde sem executar a jornada delegada autenticada.

## Requisitos

1. Quando `REAL_USER_JOURNEY=true`, o estado MSAL autenticado é obrigatório.
2. Estado MSAL ausente, vazio ou inválido deve encerrar a execução com erro explícito.
3. O workflow não pode transformar ausência de credencial de sessão em `skip` bem-sucedido.
4. A mudança não concede permissões Microsoft Graph, não cria segredo e não altera ambiente.
5. O aceite funcional continua dependendo da permissão delegada exigida pelo endpoint de conexões.

## Critérios de aceite

1. `frontend/tests/e2e/wsjf-planner-excel-conexoes-live.spec.js` falha quando a jornada real é solicitada sem estado autenticado válido.
2. O workflow `WSJF conexoes - sessao MSAL real` falha cedo quando `WSJF_MSAL_STORAGE_STATE_B64` não estiver disponível.
3. O aceite positivo só é válido quando Planner e Excel Online aparecem conectados na jornada real.
4. Nenhum falso positivo por `skip` é aceito no modo de jornada real.
5. Nenhum consentimento, segredo ou deploy é executado por este incremento.
