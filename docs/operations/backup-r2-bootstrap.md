# Bootstrap R2 e captura da evidência DEV

Este procedimento configura os cinco secrets pendentes, executa o backup real do banco SQLite DEV e captura os artifacts necessários para o gate DEV → STG.

## Estado inicial esperado

- `FLY_API_TOKEN` já configurado;
- PRs de readiness e rollout preferencialmente mergeadas;
- GitHub CLI autenticado com permissão administrativa no repositório;
- Node.js/NPM disponíveis para executar Wrangler;
- conta Cloudflare com R2 habilitado.

## Credenciais R2

No Cloudflare R2, crie um token S3 com permissão **Object Read & Write** limitada somente ao bucket usado pelo ReqSys. Copie imediatamente:

- Account ID;
- Access Key ID;
- Secret Access Key.

O Secret Access Key não poderá ser consultado novamente depois que a tela for fechada.

## Execução única

Na raiz do repositório:

```bash
python scripts/bootstrap_reqsys_r2_backup.py --bucket reqsys-backups
```

O script:

1. verifica `gh`, `npx` e autenticação GitHub;
2. verifica ou cria o bucket privado `reqsys-backups` usando Wrangler;
3. solicita Account ID, Access Key ID e Secret Access Key;
4. gera localmente um `RESTIC_PASSWORD` criptograficamente aleatório;
5. envia os cinco valores diretamente por `stdin` para `gh secret set`;
6. não grava arquivo `.env`, payload ou segredo em disco;
7. executa o Provider Readiness quando disponível na `main`;
8. executa `ReqSys Free Tier Backup` somente para `dev`;
9. aguarda o run terminar e exige o artifact `reqsys-backup-evidence-dev`;
10. executa o gate DEV → STG quando disponível;
11. imprime somente URLs, nomes de artifacts e estado sanitizado.

## Secrets materializados

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
RESTIC_PASSWORD
```

## Guard rails

- `FLY_API_TOKEN` não é alterado;
- STG não é habilitado pelo bootstrap;
- PROD não é selecionado, acessado ou habilitado;
- o script não imprime nem persiste os valores secretos;
- o workflow de backup inicializa o repositório Restic automaticamente quando necessário;
- somente uma evidência DEV válida permite que o workflow de rollout proponha uma PR para STG.

## Evidências esperadas

Ao final, o run do backup precisa conter:

```text
reqsys-backup-evidence-dev
reqsys-backup-real-coverage-dashboard
```

O artifact DEV deve comprovar `quick_check`, SHA-256, restauração isolada, RPO, RTO, quota, snapshot e `correlation_id`.

`production_touched=false`
