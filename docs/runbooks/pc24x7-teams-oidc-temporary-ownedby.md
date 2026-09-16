# PC24x7 Teams — ciclo temporário `Application.ReadWrite.OwnedBy`

## Objetivo

Criar/revalidar a FIC OIDC do GitHub Environment `development` em DEV sem conceder automaticamente `Application.ReadWrite.All` ao CI.

## Princípio de menor privilégio

A permissão `Application.ReadWrite.OwnedBy` só é usada quando a identidade mutadora é proprietária da App Registration alvo. Se ownership não estiver comprovado, o fluxo falha fechado e exige decisão humana. A automação nunca promove para `Application.ReadWrite.All`.

## Fluxo

1. Uma sessão administrativa Microsoft Entra já autenticada executa o orquestrador local.
2. O orquestrador valida tenant, aplicação, service principal e ownership.
3. Se já houver `Application.ReadWrite.OwnedBy`, o fluxo aborta para não revogar permissão preexistente por engano.
4. O orquestrador cria uma appRoleAssignment temporária `Application.ReadWrite.OwnedBy` para a identidade mutadora.
5. Dispara `PC24x7 Teams OIDC Environment Bootstrap` na `main`.
6. O workflow autentica via OIDC usando a identidade mutadora e cria/revalida somente a FIC `environment:development`.
7. O orquestrador relê a FIC por uma fonte independente.
8. Em `finally`, revoga apenas a appRoleAssignment criada nesta execução e relê o estado para comprovar ausência.

## Bloqueios fail-closed

- tenant divergente;
- identidade mutadora não proprietária da aplicação;
- `OwnedBy` já presente antes da execução;
- workflow em SHA diferente da `main` capturada;
- workflow não verde;
- FIC ausente ou divergente;
- falha ao revogar ou comprovar revogação.

## Ação humana mínima

A sessão administrativa precisa ter privilégio suficiente para criar/remover a appRoleAssignment temporária. Nenhuma senha, token, client secret ou MFA deve ser fornecido ao script ou registrado em logs. A autenticação ocorre fora do script e os valores sensíveis permanecem no mecanismo de sessão do Microsoft Entra/GitHub.

## Escopo

Somente DEV. TEST/HML/PROD não são alterados. O fluxo não cria App Registration, não cria segredo, não muda RBAC Azure, não altera API permissions para `Application.ReadWrite.All` e não realiza deploy.
