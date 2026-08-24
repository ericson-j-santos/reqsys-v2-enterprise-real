# Blueprint — Credential Control Plane Lifecycle

## 1. Objetivo

Evoluir o **Credential & Environment Control Plane** já existente no ReqSys para governar também o ciclo de vida de credenciais externas, sem criar outro cofre, outro catálogo concorrente ou armazenar tokens no repositório.

Escopo deste incremento:

- GitLab mirror: Project Access Token com `write_repository + self_rotate`;
- Fly.io: deploy tokens restritos por app e rotacionados por um controlador governado;
- Azure Key Vault: fonte externa de verdade dos valores secretos;
- GitHub Actions: identidade federada por OIDC para acessar o Key Vault;
- política, planejamento, execução, auditoria e fail-closed;
- nenhuma migração em massa dos consumidores existentes neste incremento.

## 2. O que já existia e foi preservado

O ReqSys já possui:

- `config/credential-control-plane.json`: catálogo canônico de credencial → ambiente → consumidor;
- `scripts/validate_credential_control_plane.py`: gate estrutural fail-closed;
- `scripts/project_credential_control_plane_health.py`: saúde runtime metadata-only;
- `scripts/build_credential_control_plane_dashboard.py`: dashboard autocontido;
- `backend/app/core/identity_governance.py`: política de identidade e slots `current/next`;
- cofre local e APIs de service tokens;
- mirror GitHub → GitLab fail-closed;
- múltiplos workflows Fly que ainda dependem de `secrets.FLY_API_TOKEN`.

Este incremento **não substitui** esses componentes. Ele adiciona o plano de lifecycle mutável ao mesmo domínio.

## 3. Arquitetura alvo

```text
GitHub Actions
     │
     │ OIDC (sem client secret de longa duração)
     ▼
Azure Entra ID
     │
     ▼
Azure Key Vault
     │
     ├── reqsys-gitlab-main-mirror-token
     │       └── GitLab self_rotate
     │
     ├── reqsys-fly-control-plane-org-token   [bootstrap/controlador]
     │       ├── reqsys-api-dev
     │       ├── reqsys-app-dev
     │       ├── reqsys-api-stg
     │       ├── reqsys-app-stg
     │       ├── reqsys-api
     │       └── reqsys-app
     │
     └── metadados seguros
             ├── rotated_at
             ├── provider_token_id
             ├── credential_id
             └── expiração
```

O GitHub recebe apenas identificadores não secretos necessários ao OIDC. Os valores das credenciais administradas permanecem no Key Vault durante o ciclo normal.

## 4. Guard rails

A implementação é fail-closed:

- `plan` é o modo padrão;
- `execute` exige `CCP_MUTATION_ENABLED=true`;
- auto-rotação exige adicionalmente `CCP_AUTO_ROTATE=true`;
- ausência de OIDC/Key Vault bloqueia a execução;
- fallback para GitHub Actions Secret é proibido pela política;
- valor secreto no catálogo é proibido;
- GitLab expirado não tenta `self_rotate`: exige novo bootstrap;
- Fly não rotaciona sem a credencial emissora;
- Fly não substitui token existente sem `provider_token_id` que permita revogar o anterior;
- Fly valida o novo token antes de persistir e revogar o anterior;
- nenhuma evidência contém token, senha ou client secret.

## 5. Bootstrap humano — uma vez por trust chain

### 5.1 Azure / OIDC

Pré-requisitos:

- App Registration dedicada ao Credential Control Plane;
- Azure Key Vault dedicado ou explicitamente aprovado para o ReqSys;
- federated credential limitada ao repositório `ericson-j-santos/reqsys-v2-enterprise-real` e à branch `main`;
- permissão mínima no Key Vault para ler e gravar os secrets administrados.

Cadastrar como **GitHub Actions Variables**, nunca como secrets de credencial:

```text
CCP_AZURE_CLIENT_ID=<client id da identidade dedicada>
CCP_AZURE_TENANT_ID=<tenant id>
CCP_AZURE_SUBSCRIPTION_ID=<subscription id>
REQSYS_KEY_VAULT_NAME=<nome do vault>
CCP_ENABLED=true
CCP_MUTATION_ENABLED=false
CCP_AUTO_ROTATE=false
```

Critério de conclusão: execução `plan` autentica por OIDC e consegue consultar os recursos autorizados no Key Vault.

### 5.2 GitLab mirror

Criar uma vez o Project Access Token dedicado:

```text
name: reqsys-github-mirror
scopes:
  - write_repository
  - self_rotate
```

Armazenar somente no Key Vault:

```text
reqsys-gitlab-main-mirror-token
```

Registrar `rotated_at` e expiração coerente com a política. Não copiar o valor para documentação, Issue, PR, artifact ou logs.

Critério de conclusão: `plan --provider gitlab` retorna `HEALTHY` ou `ROTATION_DUE`, nunca `BOOTSTRAP_REQUIRED`.

### 5.3 Fly.io controlador

Criar uma credencial org-scoped dedicada para emitir/substituir os deploy tokens app-scoped. Após confirmar a organização com `fly orgs list`:

```bash
fly tokens create org --org <ORGANIZACAO> --expiry 720h --name reqsys-control-plane --json
```

Armazenar somente no Key Vault:

```text
reqsys-fly-control-plane-org-token
```

Essa credencial é o bootstrap/controlador e possui blast radius maior que os deploy tokens por app. Não deve ser distribuída aos workflows de deploy.

Critério de conclusão: `plan --provider fly` identifica tokens app-scoped ausentes como `CREATE`, sem `BOOTSTRAP_REQUIRED` para o emissor.

> **Limitação confirmada da Fly (2026-08-23):** tokens `org` (`fly tokens create org`) **não têm permissão de emitir outros tokens** — a mutação `createLimitedAccessToken` retorna `Not authorized to access this createlimitedaccesstoken` quando invocada com um token org como emissor. Confirmado tanto em execução real do workflow (`execute --provider fly`) quanto na comunidade oficial da Fly ([community.fly.io/t/org-api-token-cannot-create-deploy-tokens](https://community.fly.io/t/org-api-token-cannot-create-deploy-tokens/18602)). É uma restrição deliberada do modelo de macaroons da Fly (evita autoelevação de um token restrito), não um bug de configuração.
>
> A alternativa óbvia — usar o `fly auth token` (o antigo "personal access token" de sessão) como emissor — **não é viável**: a própria Fly marca esse comando como *deprecated* e documenta que o token "pode expirar rapidamente e não deve ser usado em lugares que precisam continuar funcionando por muito tempo".
>
> **Consequência prática:** `reqsys-fly-control-plane-org-token` continua útil só para `validate_app`/leitura de status, não como emissor automático dos 6 deploy tokens app-scoped. A criação/rotação desses 6 tokens (`fly-api-dev-deploy`, `fly-app-dev-deploy`, `fly-api-hml-deploy`, `fly-app-hml-deploy`, `fly-api-prod-deploy`, `fly-app-prod-deploy`) permanece uma ação humana periódica (a cada `interval_days: 30`, quando `plan` reportar `ROTATION_DUE`), até a Fly expor algum mecanismo de identidade delegável para isso. `execute --provider fly` deve ser tratado como bloqueado por design até então.

## 6. Ativação segura

Executar nesta ordem:

1. definir `CCP_ENABLED=true`;
2. manter `CCP_MUTATION_ENABLED=false` e `CCP_AUTO_ROTATE=false`;
3. disparar `Credential Control Plane Lifecycle` em `plan`;
4. resolver todos os `BLOCKED`/`BOOTSTRAP_REQUIRED`;
5. habilitar `CCP_MUTATION_ENABLED=true`;
6. executar manualmente `execute` primeiro para `gitlab`, depois para `fly`;
7. validar artifacts e acesso real das novas credenciais;
8. somente após evidência verde, habilitar `CCP_AUTO_ROTATE=true`.

## 7. Migração dos consumidores

O repositório ainda possui vários workflows usando `secrets.FLY_API_TOKEN` e o mirror usa `secrets.GITLAB_MIRROR_TOKEN`.

Não remover esses secrets no mesmo incremento do lifecycle. A migração deve ocorrer em lotes pequenos:

1. escolher um consumidor DEV;
2. trocar sua obtenção de token para OIDC → Key Vault;
3. executar o workflow e validar runtime;
4. repetir para os demais consumidores DEV;
5. promover o padrão para HML;
6. promover para PROD;
7. migrar o GitLab mirror;
8. confirmar que não existe mais referência aos antigos repository secrets;
9. somente então revogar/remover os secrets legados.

## 8. Operação

Validação do contrato:

```bash
python scripts/credential_control_plane_lifecycle.py --mode validate
```

Planejamento GitLab:

```bash
python scripts/credential_control_plane_lifecycle.py --mode plan --provider gitlab
```

Planejamento Fly:

```bash
python scripts/credential_control_plane_lifecycle.py --mode plan --provider fly
```

Para mutação, preferir `workflow_dispatch` depois do bootstrap e dos gates verdes.

## 9. Evidência esperada

Artifact:

```text
audit/credential-control-plane-lifecycle.json
```

Contrato de segurança:

```json
{
  "security": {
    "secret_values_exposed": false,
    "secret_values_persisted_in_evidence": false,
    "github_secret_fallback_used": false
  }
}
```

`results` contém apenas identificadores, status, expiração e IDs de provedor necessários à governança; nunca o token.

## 10. Critério de conclusão do programa

A rotina manual só estará eliminada quando:

- OIDC → Key Vault estiver validado;
- GitLab autorrotacionar sem acesso humano ao portal;
- Fly gerar/validar/substituir deploy tokens app-scoped de modo governado;
- todos os workflows consumidores lerem suas credenciais do control plane;
- `secrets.GITLAB_MIRROR_TOKEN` e os `secrets.FLY_API_TOKEN` legados deixarem de ser necessários;
- alertas de vencimento, auditoria e evidence estiverem ativos;
- não existir fallback para token pessoal.

Até esse cutover, o estado é **transicional** e os secrets legados devem permanecer disponíveis aos consumidores ainda não migrados.
