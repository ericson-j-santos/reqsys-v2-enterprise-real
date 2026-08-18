# Teams Graph app-only — identidade governada

O caminho `graph_app_only` do Teams passa a resolver sua App Registration exclusivamente pelo `ApplicationIdentityRegistry`.

## Perfil obrigatório

O catálogo indicado por `REQSYS_IDENTITY_GOVERNANCE_FILE` deve possuir exatamente um perfil por ambiente com:

- `purpose`: `teams-proactive-messaging`
- `data_classification`: `confidential`
- `environment`: `development`, `staging` ou `production`, conforme `APP_ENV`
- `tenant_id` e `client_id` da App Registration dedicada ao Teams
- `current_secret_ref` e `next_secret_ref` distintos
- credencial dentro do prazo de rotação

A aplicação bloqueia a operação quando o perfil não existe, é ambíguo, está vencido ou o segredo atual não pode ser resolvido.

## Referências de segredo

Suportadas neste incremento:

- `env://NOME_VARIAVEL`: lê somente a variável informada;
- `github-secret://NOME_VARIAVEL`: espera que o secret tenha sido injetado como variável pelo workflow/deploy;
- `vault://chave`: tenta o vault local e depois o vault-service remoto.

`keyvault://` permanece bloqueado até existir um provider explícito no backend. Não há fallback para outra Application mais privilegiada.

## Escopo

Migrado neste incremento:

- obtenção de token app-only do Microsoft Graph para Teams;
- envio `graph_app_only`;
- criação app-only de chat utilizada pelo fluxo 1:1;
- evidência sanitizada do perfil usado, sem token ou client secret.

Não alterado:

- login/MSAL e token delegado;
- webhook Teams;
- Power Automate `flow_bot`;
- Azure Bot / Bot Framework;
- SharePoint, Dataverse e Power Automate que ainda usam a identidade anterior.

## Exemplo DEV

```json
{
  "name": "reqsys-dev-teams-confidential",
  "environment": "development",
  "purpose": "teams-proactive-messaging",
  "data_classification": "confidential",
  "tenant_id": "<tenant-id>",
  "client_id": "<client-id-dedicado-teams>",
  "current_secret_ref": "vault://reqsys/dev/teams/client-secret-current",
  "next_secret_ref": "vault://reqsys/dev/teams/client-secret-next",
  "rotated_at": "<data-UTC>",
  "max_age_days": 60
}
```

O arquivo real não deve ser commitado com segredos. O valor da credencial permanece somente no provider indicado pela referência.
