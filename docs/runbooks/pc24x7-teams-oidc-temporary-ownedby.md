# PC24x7 Teams — automação temporária de `Application.ReadWrite.OwnedBy`

## Objetivo

Criar/revalidar a FIC `repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:development` sem conceder automaticamente `Application.ReadWrite.All` ao CI.

## Desenho

1. Uma sessão administrativa Microsoft Entra já autenticada valida tenant, App Registration, service principal e ownership.
2. Se `Application.ReadWrite.OwnedBy` já existir, o fluxo aborta para não revogar permissão preexistente por engano.
3. A sessão administrativa cria uma appRoleAssignment temporária `Application.ReadWrite.OwnedBy` para a identidade mutadora.
4. O orquestrador dispara `PC24x7 Teams OIDC Environment Bootstrap` na `main`.
5. O workflow autentica via OIDC como a própria identidade mutadora usando o subject já confiado da `main`.
6. Essa identidade cria/revalida somente a FIC do Environment `development`.
7. A sessão administrativa relê a FIC por uma fonte independente.
8. Em `finally`, o orquestrador revoga somente a appRoleAssignment criada nesta execução.
9. A releitura final deve comprovar que `OwnedBy` não permanece atribuída.

## Guardrails

- a automação nunca promove para `Application.ReadWrite.All`;
- se a identidade mutadora não for owner da aplicação alvo, o fluxo falha fechado com `MUTATOR_NOT_OWNER`;
- ownership deve ser corrigido explicitamente em vez de ampliar a permissão do CI;
- uma permissão `OwnedBy` preexistente nunca é revogada implicitamente;
- nenhum segredo, senha, MFA ou token é aceito por argumento;
- o workflow não usa `environment: development`, preservando o subject OIDC já confiado da `main`;
- TEST/HML/PROD não são alterados.

## Pré-requisitos

- Azure CLI autenticado em uma conta administrativa autorizada no tenant correto;
- GitHub CLI autenticado para disparar o workflow;
- identidade mutadora como owner da App Registration alvo;
- script e workflow integrados à `main`.

## Evidência mínima

A execução só termina `ready` quando comprova:

- tenant correto;
- ownership;
- ausência de `OwnedBy` preexistente;
- grant temporário criado e relido;
- workflow verde no SHA exato da `main` capturada;
- FIC com issuer, subject e audience exatos;
- grant temporário removido;
- releitura final sem a permissão temporária;
- `application_readwrite_all_granted=false`;
- `secret_value_exposed=false`.
