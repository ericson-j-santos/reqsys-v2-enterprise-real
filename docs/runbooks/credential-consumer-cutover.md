# Blueprint — Cutover dos consumidores para o Credential Control Plane

## 1. Objetivo

Eliminar dos consumidores migrados a dependência direta de `secrets.FLY_API_TOKEN` e `secrets.GITLAB_MIRROR_TOKEN`, usando o Azure Key Vault como fonte externa de verdade e GitHub Actions OIDC como identidade de acesso.

Este incremento complementa o lifecycle criado na PR #1281. A PR #1281 já cria/rotaciona credenciais gerenciadas; este cutover faz os workflows passarem a consumi-las com identidades de leitura separadas da identidade mutadora.

## 2. Estado alvo

```text
                         Microsoft Entra ID
                                 |
       +-------------------------+-------------------------+
       |                         |                         |
       v                         v                         v
Lifecycle mutator         GitLab reader             Fly readers
CCP_AZURE_CLIENT_ID       ..._GITLAB        ..._DEV / ..._HML / ..._PROD
       |                         |                         |
       +-------------------------+-------------------------+
                                 |
                                 v
                         Azure Key Vault
                                 |
       +-------------------------+-------------------------+
       |                         |                         |
  issuer/bootstrap          GitLab token          Fly app-scoped tokens
```

Princípio: a validação `credential_id -> consumer` feita no código é defesa adicional, não fronteira de segurança. A fronteira real deve existir em Entra ID + Key Vault RBAC.

O valor secreto:

- não é versionado;
- não é publicado em artifact;
- é mascarado no GitHub Actions;
- é exportado somente para `GITHUB_ENV` no job que o utiliza;
- não possui fallback para GitHub Secret legado;
- falha fechado se a identidade, Key Vault, vínculo de consumer, estado ou expiração forem inválidos.

## 3. Consumidores incluídos neste incremento

| Workflow | Credencial gerenciada | Identidade Azure de leitura |
|---|---|---|
| `gitlab-main-mirror.yml` | `gitlab-main-mirror` | `CCP_AZURE_CLIENT_ID_GITLAB` |
| `fly-runtime-p0.yml` | `fly-api-prod-deploy` | `CCP_AZURE_CLIENT_ID_PROD` |
| `deploy-staging-auth-fix.yml` backend | `fly-api-hml-deploy` | `CCP_AZURE_CLIENT_ID_HML` |
| `deploy-staging-auth-fix.yml` frontend | `fly-app-hml-deploy` | `CCP_AZURE_CLIENT_ID_HML` |
| `deploy-production-sync.yml` backend/config | `fly-api-prod-deploy` | `CCP_AZURE_CLIENT_ID_PROD` |
| `deploy-production-sync.yml` frontend | `fly-app-prod-deploy` | `CCP_AZURE_CLIENT_ID_PROD` |
| `fly-enterprise-sync.yml` DEV | API/frontend DEV | `CCP_AZURE_CLIENT_ID_DEV` |
| `fly-enterprise-sync.yml` HML | API/frontend HML | `CCP_AZURE_CLIENT_ID_HML` |
| `fly-enterprise-sync.yml` PROD | API/frontend PROD | `CCP_AZURE_CLIENT_ID_PROD` |

## 4. Secrets esperados no Azure Key Vault

A política canônica exige os seguintes nomes:

- `reqsys-gitlab-main-mirror-token`
- `reqsys-fly-api-dev-deploy-token`
- `reqsys-fly-app-dev-deploy-token`
- `reqsys-fly-api-hml-deploy-token`
- `reqsys-fly-app-hml-deploy-token`
- `reqsys-fly-api-prod-deploy-token`
- `reqsys-fly-app-prod-deploy-token`

Credencial controladora de bootstrap/lifecycle, não usada diretamente pelos deploys:

- `reqsys-fly-control-plane-org-token`

## 5. Variáveis GitHub obrigatórias

Variáveis comuns, sem conteúdo secreto:

- `CCP_AZURE_TENANT_ID`
- `CCP_AZURE_SUBSCRIPTION_ID`
- `REQSYS_KEY_VAULT_NAME`
- `CCP_ENABLED=true`

Identidades separadas:

- `CCP_AZURE_CLIENT_ID` — **somente lifecycle mutador** já criado pela #1281;
- `CCP_AZURE_CLIENT_ID_GITLAB` — reader do secret de mirror GitLab;
- `CCP_AZURE_CLIENT_ID_DEV` — reader dos dois deploy tokens DEV;
- `CCP_AZURE_CLIENT_ID_HML` — reader dos dois deploy tokens HML/STG;
- `CCP_AZURE_CLIENT_ID_PROD` — reader dos dois deploy tokens PROD.

Esses Client IDs não são segredos. Mesmo assim, a autorização não deve ser baseada no conhecimento do ID: deve ser limitada pelo `sub` OIDC e pelo RBAC da identidade no Key Vault.

A mutação do lifecycle continua separada e exige explicitamente:

- `CCP_MUTATION_ENABLED=true` somente para execução governada;
- `CCP_AUTO_ROTATE=true` somente depois de plan/execute/smokes aprovados.

## 6. OIDC — federação obrigatória

O repositório foi criado em 03/05/2026, antes da mudança do GitHub de 15/07/2026 para subjects imutáveis por padrão. Portanto, salvo opt-in posterior, rename/transfer relevante ou customização de claims, os subjects esperados seguem o formato histórico abaixo.

### Lifecycle mutador

App Registration associada a `CCP_AZURE_CLIENT_ID`:

```text
repo:ericson-j-santos/reqsys-v2-enterprise-real:ref:refs/heads/main
```

### GitLab reader

App Registration associada a `CCP_AZURE_CLIENT_ID_GITLAB` para o mirror efetivo em `main`:

```text
repo:ericson-j-santos/reqsys-v2-enterprise-real:ref:refs/heads/main
```

Mesmo subject, **App Registration distinta** e RBAC distinto.

### Fly readers

App Registrations distintas para os GitHub Environments:

```text
CCP_AZURE_CLIENT_ID_DEV  -> repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:dev
CCP_AZURE_CLIENT_ID_HML  -> repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:staging
CCP_AZURE_CLIENT_ID_PROD -> repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:production
```

### Validação obrigatória antes do cutover real

Antes de cadastrar as federated credentials no Entra ID, confirmar o `sub` efetivamente emitido pelo GitHub. Repositórios que adotaram subjects imutáveis usam owner/repository IDs no segmento `repo`; não cadastrar confiança mais ampla para contornar incompatibilidade.

Issuer esperado:

```text
https://token.actions.githubusercontent.com
```

Audience usado pelo `azure/login`:

```text
api://AzureADTokenExchange
```

## 7. Permissões Azure / Key Vault

Aplicar menor privilégio por identidade:

| Identidade | Acesso máximo esperado |
|---|---|
| Lifecycle mutator | secrets gerenciados + issuer necessários para criar/rotacionar/revogar |
| GitLab reader | leitura de `reqsys-gitlab-main-mirror-token` |
| DEV reader | leitura de `reqsys-fly-api-dev-deploy-token` e `reqsys-fly-app-dev-deploy-token` |
| HML reader | leitura de `reqsys-fly-api-hml-deploy-token` e `reqsys-fly-app-hml-deploy-token` |
| PROD reader | leitura de `reqsys-fly-api-prod-deploy-token` e `reqsys-fly-app-prod-deploy-token` |

Não conceder ao reader DEV/HML/PROD permissão para criar, atualizar, excluir ou listar secrets que não pertençam ao seu trust boundary. Não usar o App Registration mutador do lifecycle nos workflows de deploy/mirror.

## 8. Ordem segura de implantação

1. Confirmar o subject OIDC real do repositório e environments.
2. Manter/provisionar a App Registration mutadora do lifecycle (`CCP_AZURE_CLIENT_ID`).
3. Criar quatro App Registrations readers: GitLab, DEV, HML e PROD.
4. Criar as federated credentials com os subjects exatos da seção 6.
5. Aplicar RBAC mínimo por reader no Key Vault conforme a seção 7.
6. Configurar `CCP_AZURE_CLIENT_ID_GITLAB`, `..._DEV`, `..._HML`, `..._PROD` no GitHub.
7. Garantir que os sete secrets gerenciados existem no Key Vault.
8. Executar `Credential Control Plane Lifecycle` em `plan`.
9. Se o plano estiver consistente, executar `execute` manualmente para materializar/rotacionar as credenciais necessárias.
10. Executar `Credential Control Plane Cutover Smoke` para os seis alvos Fly antes do merge:
    - `fly-api-dev`
    - `fly-app-dev`
    - `fly-api-hml`
    - `fly-app-hml`
    - `fly-api-prod`
    - `fly-app-prod`
11. O smoke `gitlab` usa a identidade do mirror e deve ser executado em `main`; validar no primeiro run governado após merge ou por uma execução autorizada com subject explicitamente provisionado e removido depois. Não ampliar o subject apenas para viabilizar teste.
12. Validar CI completo da PR e mergeabilidade.
13. Somente depois fazer merge.
14. Após merge, validar o mirror GitHub→GitLab com a identidade reader dedicada e exigir evidence verde.
15. Remover os GitHub Secrets legados somente quando uma busca final provar que não existem consumidores que ainda dependem deles.

## 9. Evidência esperada

Cada resolução gera JSON sanitizado contendo:

- `status`;
- `source=azure_key_vault`;
- `credential_id`;
- `consumer`;
- `provider`;
- nome lógico do secret;
- expiração;
- SHA-256 do valor para correlação sem exposição;
- `legacy_github_secret_fallback=false`;
- `secret_value_exposed=false`.

O artifact nunca deve conter o token em claro.

## 10. Critério de conclusão

O incremento só está concluído quando:

- [ ] CI da PR está verde;
- [ ] os cinco workflows migrados não referenciam `secrets.FLY_API_TOKEN` nem `secrets.GITLAB_MIRROR_TOKEN`;
- [ ] workflows consumidores não usam `CCP_AZURE_CLIENT_ID` reservado ao mutador;
- [ ] 6/6 smokes Fly resolvem credencial via Key Vault e validam o provider sem mutação;
- [ ] lifecycle `plan` está verde;
- [ ] rotação real possui evidência sanitizada;
- [ ] após merge, mirror GitHub→GitLab funciona com `CCP_AZURE_CLIENT_ID_GITLAB`;
- [ ] deploy DEV/HML/PROD usa readers separados e tokens Fly app-scoped corretos;
- [ ] nenhum secret foi exposto em log/artifact;
- [ ] GitHub Secrets legados só são removidos após inventário residual.

## 11. Escopo residual deliberado

Uma busca no repositório ainda encontra `FLY_API_TOKEN` em workflows/scripts de backup, diagnóstico, rollback, configuração e outras operações. Nem todos esses usos podem ser substituídos por deploy tokens app-scoped, pois algumas operações exigem autoridade diferente.

Esses consumidores ficam fora deste cutover para evitar redução incorreta de permissão ou quebra operacional. O próximo incremento deve classificar cada uso residual por operação/provider scope e criar credenciais dedicadas antes de eliminar o último token amplo.

## 12. Fail-closed

Se qualquer pré-condição externa estiver ausente — OIDC, Key Vault, RBAC, reader dedicado, secret gerenciado, expiração válida ou consumer autorizado — o workflow deve falhar. Não reintroduzir `secrets.FLY_API_TOKEN`/`GITLAB_MIRROR_TOKEN` nem a identidade mutadora como fallback apenas para tornar o pipeline verde.
