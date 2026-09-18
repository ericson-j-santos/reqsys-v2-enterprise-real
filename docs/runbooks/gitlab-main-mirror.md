# Runbook — Mirror governado GitHub → GitLab

## Objetivo

Manter `main` do GitLab alinhada à `main` do GitHub sem sincronização bidirecional e sem `force-push`.

## Fonte canônica

- GitHub: `ericson-j-santos/reqsys-v2-enterprise-real`, branch `main`.
- GitLab: `ericson-j-santos/reqsys-v2-enterprise-real`, branch `main`.
- Direção permitida: GitHub → GitLab.
- Alterações exclusivas no GitLab devem bloquear o mirror até reconciliação humana.

## Credencial

A credencial é gerenciada pelo Credential Control Plane, não por secret do GitHub. O fallback legado de secret está desabilitado (`allow_github_secret_fallback: false` em `config/control-plane-lifecycle-policy.json`).

- `credential_id`: `gitlab-main-mirror`
- Segredo no Azure Key Vault: `reqsys-gitlab-main-mirror-token`
- Consumidor autorizado: `github-actions:gitlab-main-mirror`
- Resolução: `.github/actions/resolve-managed-credential` via OIDC, exportando `GITLAB_MIRROR_TOKEN` apenas no runner.

A identidade deve ser técnica dedicada, com privilégio mínimo necessário para atualizar o repositório GitLab. Não reutilizar tokens de governança, deploy ou usuário pessoal.

O valor nunca deve ser armazenado em arquivo, issue, PR, log ou artifact.

## Identidade técnica do mirror

Quando existem identidades homônimas (`reqsys-github-mirror` Guest e Maintainer, por exemplo), a pergunta operacional é qual delas responde pelo token do cofre. Isso é resolvido por atestação automática, sem revelar o segredo:

```bash
GITLAB_MIRROR_TOKEN=... python scripts/attest_gitlab_mirror_identity.py
```

O script é **somente leitura**: consulta `GET /user`, os metadados do próprio token, a associação no projeto, as identidades homônimas e a configuração da branch protegida. Ele não altera identidade, permissão nem proteção de branch — a automação não eleva o próprio privilégio no GitLab.

Evidência gerada: `audit/gitlab-mirror-identity-attestation.json`.

Vereditos:

- `authorized`: identidade autoritativa habilitada a fast-forward na branch protegida, com force-push proibido;
- `insufficient_permission`: identidade resolvida, mas sem allowance de push na branch protegida;
- `force_push_enabled`: push permitido, porém `allow_force_push` habilitado — regressão de governança;
- `undetermined`: privilégio atual não permite ler a configuração de proteção;
- `unresolved`: credencial ausente, revogada ou sem identidade correspondente.

### Provisionamento governado da permissão

A concessão da identidade do mirror é executada pelo provisionador `gitlab/scripts/provision_gitlab_governance.py` usando exclusivamente `GITLAB_PROVISIONING_TOKEN`, nunca o próprio token do mirror.

Parâmetros versionados no job de governança:

```text
MIRROR_USER_ID=41627393
MIRROR_NAME=reqsys-github-mirror
```

O GitLab gera automaticamente o `username` de project access tokens. Por isso a correlação governada usa o identificador imutável do usuário (`41627393`) mais o nome exibido estável (`reqsys-github-mirror`), em vez de assumir que o nome exibido também é o `username`.

O provisionador:

1. confirma que `41627393` é membro ativo do projeto, com acesso suficiente, e possui o nome exibido `reqsys-github-mirror`;
2. recusa o identificador legado `41625052`;
3. recusa permissão genérica de push para `Developer`;
4. preserva os allowances existentes da branch;
5. adiciona apenas `{user_id: 41627393}` em `allowed_to_push` quando necessário;
6. mantém `allow_force_push=false`;
7. relê a branch protegida após a escrita;
8. falha se o usuário não tiver sido persistido, se uma regra anterior desaparecer ou se force-push permanecer habilitado.

O dry-run é automático e não escreve. O job `gitlab_governance_provision_apply` continua manual/protegido porque realiza alteração administrativa real. A autorização operacional para executar esse job deve ser explícita e vinculada à identidade acima.

Após a aplicação, a comprovação independente continua sendo:

```bash
GITLAB_MIRROR_TOKEN=... python scripts/attest_gitlab_mirror_identity.py --require-authorized
```

Saída `0` confirma o estado esperado; saída `2` indica que a autorização ainda não está aplicada ou não pode ser comprovada.

O workflow `.github/workflows/gitlab-mirror-identity-attestation.yml` executa a mesma atestação sob demanda (`workflow_dispatch`, com opção `require_authorized`) e em reverificação diária não bloqueante, publicando o veredito no summary da execução. O workflow do mirror também executa a atestação automaticamente quando o job falha, para que a evidência de falha nomeie a identidade efetiva.

## Execução

O workflow `.github/workflows/gitlab-main-mirror.yml` executa automaticamente após `push` na `main` e também permite `workflow_dispatch` em modo `dry_run`.

O script `scripts/sync_gitlab_mirror.py`:

1. resolve o SHA da fonte;
2. busca a `main` atual do GitLab;
3. retorna `noop` quando os SHAs já são iguais;
4. permite somente fast-forward quando o SHA GitLab é ancestral do SHA GitHub;
5. bloqueia quando houver commit exclusivo ou histórico divergente no GitLab;
6. nunca usa `--force`;
7. após o push, busca novamente a branch remota e confirma igualdade de SHA;
8. grava `audit/gitlab-mirror-sync.json` com `correlation_id`, SHAs, ação e resultado.

## Evidência esperada

Artifact GitHub Actions:

`gitlab-main-mirror-evidence-<run_id>-<attempt>`

Estados esperados:

- `passed/noop`: já sincronizado;
- `passed/fast_forward`: sincronização concluída;
- `passed/would_fast_forward`: dry-run seguro;
- `blocked/none`: divergência detectada;
- `blocked/identity_not_authorized`: a proteção da branch recusou o push porque a identidade técnica não está autorizada — ver a seção "Identidade técnica do mirror";
- `failed/none`: falha técnica ou credencial ausente.

## Recuperação de divergência

Se o mirror retornar `blocked`:

1. não executar force-push;
2. identificar commits exclusivos da `main` GitLab;
3. decidir se devem ser preservados;
4. portar a alteração necessária para uma branch/PR no GitHub;
5. após merge no GitHub, executar novamente o dry-run;
6. somente sincronizar quando GitLab voltar a ser ancestral da fonte canônica.

## Critérios de aceite operacional

- credencial gerenciada resolvida pelo Key Vault;
- provisionamento confirma explicitamente `user_id=41627393` e nome `reqsys-github-mirror`, sem permissão genérica de Developer e sem force-push;
- atestação com veredito `authorized`;
- dry-run verde;
- primeira sincronização real concluída;
- SHA GitHub = SHA GitLab após o job;
- artifact de evidência disponível;
- próxima execução em `main` ocorre automaticamente;
- divergência simulada/testada bloqueia sem alterar o GitLab.

Referências: issues #846, #854 e #1503.
