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
- `insufficient_permission`: identidade resolvida, mas sem allowance de push na branch protegida (bloqueio atual);
- `force_push_enabled`: push permitido, porém `allow_force_push` habilitado — regressão de governança;
- `undetermined`: privilégio atual não permite ler a configuração de proteção;
- `unresolved`: credencial ausente, revogada ou sem identidade correspondente.

Quando o veredito não é `authorized`, a evidência traz `remaining_human_action` com a declaração de autorização já parametrizada com o `id` e o `username` da identidade correta.

### Ação humana mínima (não automatizável)

Conceder permissão no GitLab é decisão administrativa e não pode ser executada pela automação. Após ler o veredito:

1. Em `Settings > Repository > Protected branches`, na branch `main`, incluir **apenas** o usuário identificado pela atestação em `Allowed to push and merge`.
2. Manter `Allow force push` desabilitado.
3. Não desproteger a `main` e não elevar o nível de acesso além do necessário.
4. Desativar/revogar a identidade homônima não autoritativa somente depois de confirmar que nenhum outro consumidor depende dela.

Confirmação após a concessão:

```bash
GITLAB_MIRROR_TOKEN=... python scripts/attest_gitlab_mirror_identity.py --require-authorized
```

Saída `0` confirma o estado esperado; saída `2` indica que a autorização ainda não está aplicada.

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
- atestação com veredito `authorized` (identidade única e autoritativa, sem force-push);
- dry-run verde;
- primeira sincronização real concluída;
- SHA GitHub = SHA GitLab após o job;
- artifact de evidência disponível;
- próxima execução em `main` ocorre automaticamente;
- divergência simulada/testada bloqueia sem alterar o GitLab.

Referências: issues #846, #854 e #1503.
