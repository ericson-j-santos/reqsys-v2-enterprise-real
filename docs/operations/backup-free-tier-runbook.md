# Runbook — Backup gratuito Fly.io, restic e Cloudflare R2

## Estado alvo

O ReqSys mantém uma cópia consistente do SQLite de cada ambiente, criptografa no cliente com `restic`, armazena em bucket R2 privado, restaura fora do Fly.io e publica somente evidências não sensíveis.

## Fluxo

```text
Fly Volume (/data/reqsys.db)
  -> sqlite3.Connection.backup() em arquivo temporário
  -> Fly SFTP para runner GitHub
  -> verificação PRAGMA quick_check + SHA-256 + contagem por tabela
  -> restic com criptografia no cliente
  -> Cloudflare R2 privado
  -> retenção e quota guard
  -> restauração isolada no runner
  -> comparação de SHA-256, estrutura e contagens
  -> Dashboard GitHub #1162 e Adaptive Card no Teams
```

## Ativação externa necessária

A automação entra em modo amarelo até que um bucket R2 privado e as credenciais de menor privilégio sejam cadastrados. Não há criação automática de conta Cloudflare porque isso exige aceite de termos e controle do proprietário.

Cadastre os seguintes GitHub Actions secrets:

- `FLY_API_TOKEN` — token com acesso somente aos apps ReqSys necessários;
- `R2_ACCOUNT_ID`;
- `R2_ACCESS_KEY_ID` — permissão Object Read & Write restrita ao bucket;
- `R2_SECRET_ACCESS_KEY`;
- `R2_BUCKET`;
- `RESTIC_PASSWORD` — senha forte exclusiva, mantida fora do repositório.

O endpoint S3 é montado automaticamente como:

```text
https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
```

## Rollout governado

1. DEV está habilitado no inventário e inicia automaticamente quando os secrets existirem.
2. Após uma execução DEV com backup, restauração e integridade verdes, alterar `enabled` de STG para `true`.
3. Após uma execução STG verde, habilitar PROD em PR separado e com aprovação governada.
4. Execução manual de ativo ainda desabilitado exige `include_disabled=true`; para PROD também exige `approve_prod=APROVO-PROD`.

## Quota gratuita

- saudável: abaixo de 8 GiB;
- alerta: entre 8 e 9 GiB;
- crítico: a partir de 9 GiB;
- limite técnico de segurança: 9 GiB, preservando margem antes da franquia de 10 GB-mês.

O dashboard publica `restic stats --mode raw-data` e bloqueia o gate quando a quota fica crítica.

## Retenção inicial

- 7 diários;
- 4 semanais;
- 3 mensais;
- 1 anual.

A retenção é aplicada por tag do ativo e seguida de `restic check`.

## Recuperação

1. Abra o Dashboard #1162 e localize o último `snapshot_id` saudável.
2. Execute o workflow manual para o ambiente necessário ou use `restic restore <snapshot_id> --target <diretório-isolado>` em estação autorizada.
3. Valide `PRAGMA quick_check`, SHA-256 e contagens por tabela.
4. Para recuperação Fly, crie novo volume/Machine ou siga o runbook de incidente; não sobrescreva o banco original antes da aprovação.

## Segurança

- dumps e bancos restaurados são apagados do runner ao final;
- artifacts contêm somente JSON de evidência e dashboard;
- dados não são enviados à issue ou ao Teams;
- o bucket deve permanecer privado;
- logs não podem imprimir secrets, conteúdo do banco ou URLs assinadas;
- rotacione tokens após incidente ou mudança de responsável.
