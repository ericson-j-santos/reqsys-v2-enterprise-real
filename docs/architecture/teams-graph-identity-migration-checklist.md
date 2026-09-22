# Checklist de rollout — Teams Graph app-only

## DEV

- definir `REQSYS_IDENTITY_GOVERNANCE_FILE` apontando para o catálogo real;
- cadastrar perfil `development + teams-proactive-messaging + confidential`;
- gravar o segredo atual no provider indicado por `current_secret_ref`;
- provisionar `next_secret_ref` distinto para a próxima rotação;
- validar criação de chat app-only e o modo explícito `graph_app_only`;
- confirmar que logs/respostas não contêm token nem client secret.

## STG/PROD

Repetir com App Registration dedicada por ambiente. Não reutilizar a identidade de login nem copiar o segredo de DEV.

A promoção deve permanecer bloqueada se o perfil estiver ausente, vencido ou com segredo não resolvido.
