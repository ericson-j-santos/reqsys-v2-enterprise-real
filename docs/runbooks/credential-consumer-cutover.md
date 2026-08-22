# Blueprint — Cutover dos consumidores para o Credential Control Plane

## 1. Objetivo

Eliminar dos consumidores migrados a dependência direta de `secrets.FLY_API_TOKEN` e `secrets.GITLAB_MIRROR_TOKEN`, usando o Azure Key Vault como fonte externa de verdade e GitHub Actions OIDC como identidade de acesso.

Este incremento complementa o lifecycle criado na PR #1281. A PR #1281 já cria/rotaciona credenciais gerenciadas; este cutover faz os workflows passarem a consumi-las.

## 2. Estado alvo

```text
GitHub Actions
    |
    | OIDC (sem client secret de longa duração)
    v
Microsoft Entra ID
    |
    v
Azure Key Vault
    |
    +--> token GitLab mirror
    +--> Fly API DEV
    +--> Fly frontend DEV
    +--> Fly API HML
    +--> Fly frontend HML
    +--> Fly API PROD
    +--> Fly frontend PROD
```

O valor secreto:

- não é versionado;
- não é publicado em artifact;
- é mascarado no GitHub Actions;
- é exportado somente para `GITHUB_ENV` no job que o utiliza;
- não possui fallback para GitHub Secret legado;
- falha fechado se a identidade, Key Vault, vínculo de consumer, estado ou expiração forem inválidos.

## 3. Consumidores incluídos neste incremento

| Workflow | Credencial gerenciada |
|---|---|
| `gitlab-main-mirror.yml` | `gitlab-main-mirror` |
| `fly-runtime-p0.yml` | `fly-api-prod-deploy` |
| `deploy-staging-auth-fix.yml` backend | `fly-api-hml-deploy` |
| `deploy-staging-auth-fix.yml` frontend | `fly-app-hml-deploy` |
| `deploy-production-sync.yml` backend/config | `fly-api-prod-deploy` |
| `deploy-production-sync.yml` frontend | `fly-app-prod-deploy` |
| `fly-enterprise-sync.yml` API | `fly-api-{dev|hml|prod}-deploy` |
| `fly-enterprise-sync.yml` frontend | `fly-app-{dev|hml|prod}-deploy` |

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

Configurar como repository/environment variables, sem conteúdo secreto:

- `CCP_AZURE_CLIENT_ID`
- `CCP_AZURE_TENANT_ID`
- `CCP_AZURE_SUBSCRIPTION_ID`
- `REQSYS_KEY_VAULT_NAME`
- `CCP_ENABLED=true`

A mutação do lifecycle continua separada e exige explicitamente:

- `CCP_MUTATION_ENABLED=true` somente para execução governada;
- `CCP_AUTO_ROTATE=true` somente depois de plan/execute/smokes aprovados.

## 6. OIDC — federação obrigatória

O repositório foi criado em 03/05/2026, antes da mudança do GitHub de 15/07/2026 para subjects imutáveis por padrão. Portanto, salvo opt-in posterior, rename/transfer relevante ou customização de claims, os subjects esperados seguem o formato histórico abaixo.

Para jobs sem GitHub Environment, por exemplo lifecycle/mirror em `main`:

```text
repo:ericson-j-santos/reqsys-v2-enterprise-real:ref:refs/heads/main
```

Para jobs vinculados aos GitHub Environments:

```text
repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:dev
repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:staging
repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:production
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

Para os workflows consumidores, a identidade OIDC precisa apenas ler as credenciais gerenciadas necessárias. Aplicar menor privilégio no Key Vault.

A identidade que executa lifecycle/rotação precisa de permissões adicionais de escrita, conforme PR #1281. Como endurecimento posterior, é recomendado separar a identidade read-only dos consumidores da identidade mutadora do lifecycle. Este incremento reutiliza as variáveis `CCP_AZURE_*` existentes para manter o delta Pareto pequeno; não declarar segregação de identidade como concluída até ela ser provisionada e validada.

## 8. Ordem segura de implantação

1. Confirmar o subject OIDC real do repositório e environments.
2. Provisionar/ajustar as federated credentials no Microsoft Entra ID.
3. Conceder ao principal somente acesso necessário ao Key Vault.
4. Garantir que os sete secrets gerenciados existem no Key Vault.
5. Executar `Credential Control Plane Lifecycle` em `plan`.
6. Se o plano estiver consistente, executar `execute` manualmente para materializar/rotacionar as credenciais necessárias.
7. Executar `Credential Control Plane Cutover Smoke` para cada alvo:
   - `gitlab`
   - `fly-api-dev`
   - `fly-app-dev`
   - `fly-api-hml`
   - `fly-app-hml`
   - `fly-api-prod`
   - `fly-app-prod`
8. Exigir 7/7 smokes verdes e artifacts sanitizados.
9. Validar CI completo da PR e mergeabilidade.
10. Somente depois fazer merge.
11. Após merge, validar o mirror e os deploys governados.
12. Remover os GitHub Secrets legados somente quando uma busca final provar que não existem consumidores que ainda dependem deles.

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
- [ ] os 7 alvos do smoke resolvem credencial via Key Vault e validam o provedor sem mutação;
- [ ] lifecycle `plan` está verde;
- [ ] rotação real possui evidência sanitizada;
- [ ] mirror GitHub→GitLab funciona com o token gerenciado;
- [ ] deploy DEV/HML/PROD usa tokens Fly app-scoped corretos;
- [ ] nenhum secret foi exposto em log/artifact;
- [ ] GitHub Secrets legados só são removidos após inventário residual.

## 11. Escopo residual deliberado

Uma busca no repositório ainda encontra `FLY_API_TOKEN` em workflows/scripts de backup, diagnóstico, rollback, configuração e outras operações. Nem todos esses usos podem ser substituídos por deploy tokens app-scoped, pois algumas operações exigem autoridade diferente.

Esses consumidores ficam fora deste cutover para evitar redução incorreta de permissão ou quebra operacional. O próximo incremento deve classificar cada uso residual por operação/provider scope e criar credenciais dedicadas antes de eliminar o último token amplo.

## 12. Fail-closed

Se qualquer pré-condição externa estiver ausente — OIDC, Key Vault, RBAC, secret gerenciado, expiração válida ou consumer autorizado — o workflow deve falhar. Não reintroduzir `secrets.FLY_API_TOKEN`/`GITLAB_MIRROR_TOKEN` como fallback apenas para tornar o pipeline verde.
