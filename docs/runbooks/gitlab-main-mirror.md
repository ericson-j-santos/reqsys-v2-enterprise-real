# Runbook — Mirror governado GitHub → GitLab

## Objetivo

Manter `main` do GitLab alinhada à `main` do GitHub sem sincronização bidirecional e sem `force-push`.

## Fonte canônica

- GitHub: `ericson-j-santos/reqsys-v2-enterprise-real`, branch `main`.
- GitLab: `ericson-j-santos/reqsys-v2-enterprise-real`, branch `main`.
- Direção permitida: GitHub → GitLab.
- Alterações exclusivas no GitLab devem bloquear o mirror até reconciliação humana.

## Credencial

Criar no GitHub Actions o secret `GITLAB_MIRROR_TOKEN` com credencial técnica dedicada e privilégio mínimo necessário para atualizar o repositório GitLab. Não reutilizar tokens de governança, deploy ou usuário pessoal quando houver identidade técnica disponível.

O valor nunca deve ser armazenado em arquivo, issue, PR, log ou artifact.

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

- secret dedicado configurado;
- dry-run verde;
- primeira sincronização real concluída;
- SHA GitHub = SHA GitLab após o job;
- artifact de evidência disponível;
- próxima execução em `main` ocorre automaticamente;
- divergência simulada/testada bloqueia sem alterar o GitLab.

Referências: issues #846 e #854.
