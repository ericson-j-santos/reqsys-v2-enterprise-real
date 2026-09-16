# PC24x7 Teams — automação temporária de `Application.ReadWrite.OwnedBy`

## Estado alvo

Automatizar a criação da FIC `repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:development` sem conceder automaticamente `Application.ReadWrite.All` ao CI.

## Desenho

O processo usa duas identidades em momentos distintos:

1. uma sessão administrativa humana já autenticada concede temporariamente `Application.ReadWrite.OwnedBy` à identidade mutadora;
2. o workflow GitHub Actions autentica como a própria identidade mutadora via OIDC da `main` e cria/revalida a FIC DEV;
3. a sessão administrativa relê a FIC;
4. em `finally`, o orquestrador revoga somente a appRoleAssignment criada nesta execução;
5. a sessão administrativa relê as appRoleAssignments e comprova a revogação.

Isso evita o erro de criar a FIC com a identidade administrativa e apenas "emprestar" uma permissão que a identidade mutadora nunca usaria.

## Guardrails

- `Application.ReadWrite.All` nunca é concedida automaticamente;
- se a identidade mutadora não for owner da App Registration alvo, o fluxo falha fechado;
- ownership deve ser corrigido explicitamente, em vez de usar `All` como fallback automático;
- uma permissão `OwnedBy` preexistente nunca é revogada implicitamente;
- o workflow roda sem `environment: development`, usando o subject OIDC já confiado da `main`;
- o único recurso criado/revalidado pelo workflow é a FIC do Environment `development`;
- TEST/HML/PROD não são tocados;
- nenhum segredo, senha, MFA ou token é aceito por argumento.

## Execução

Pré-condições:

- Azure CLI autenticado na conta administrativa e tenant correto;
- GitHub CLI autenticado com permissão para disparar workflow;
- identidade mutadora já é owner da App Registration alvo;
- workflow e scripts já estão integrados à `main`.

O orquestrador suporta `--dry-run` e exige confirmação literal `TEMP-OWNEDBY-PC24X7-TEAMS-DEV` para a execução real.

## Evidência mínima

A conclusão exige:

- tenant validado;
- ownership comprovado;
- ausência de `OwnedBy` preexistente;
- appRoleAssignment temporária criada e relida;
- workflow executado no SHA exato da `main` e verde;
- FIC relida com issuer, subject e audience exatos;
- appRoleAssignment temporária removida;
- releitura final confirmando ausência da permissão temporária;
- `application_readwrite_all_granted=false`;
- `secret_value_exposed=false`.
