# Runbook — Backup gratuito Fly.io, Restic e armazenamento S3 compatível

## Estado alvo

O ReqSys mantém uma cópia consistente do SQLite de cada ambiente, criptografa no cliente com `restic` e armazena em bucket privado S3 compatível. O provedor recomendado é Tigris; Cloudflare R2 permanece somente como rollback temporário.

## Fluxo

```text
Fly Volume (/data/reqsys.db)
  -> sqlite3.Connection.backup() em arquivo temporário
  -> Fly SFTP para runner GitHub
  -> PRAGMA quick_check + SHA-256 + contagem por tabela
  -> Restic com criptografia no cliente
  -> Tigris privado (S3)
  -> restauração isolada
  -> Dashboard GitHub #1162 e Adaptive Card no Teams
```

## Configuração Tigris recomendada

Crie um bucket privado por ambiente e cadastre:

### GitHub Actions secrets

- `FLY_API_TOKEN`;
- `OBJECT_STORAGE_ACCESS_KEY_ID`;
- `OBJECT_STORAGE_SECRET_ACCESS_KEY`;
- `OBJECT_STORAGE_BUCKET`;
- `RESTIC_PASSWORD`.

### GitHub Actions variables

- `OBJECT_STORAGE_ENDPOINT=https://fly.storage.tigris.dev`;
- `OBJECT_STORAGE_REGION=auto`.

Os valores secretos nunca devem ser gravados em arquivos, logs, issues ou artifacts.

## Compatibilidade e rollback

O workflow de backup aceita qualquer endpoint S3 compatível. Quando os secrets genéricos não estiverem configurados, o workflow principal ainda reconhece temporariamente os secrets legados do R2:

- `R2_ACCOUNT_ID`;
- `R2_ACCESS_KEY_ID`;
- `R2_SECRET_ACCESS_KEY`;
- `R2_BUCKET`.

A prontidão operacional usa apenas o contrato genérico. Após uma execução DEV válida no Tigris, remova o fallback R2 em incremento separado.

## Rollout governado

1. Configurar somente DEV.
2. Executar **ReqSys Backup Provider Readiness** em modo estrito.
3. Executar **ReqSys Free Tier Backup** com `environment=dev`.
4. Exigir artifact `reqsys-backup-evidence-dev` com restauração e integridade válidas.
5. Habilitar STG somente após evidência DEV.
6. Habilitar PROD somente após evidência STG e aprovação explícita.

## Quota Tigris

A franquia gratuita atual é menor que a antiga margem operacional de R2. Adotar:

- saudável: abaixo de 4 GiB;
- alerta: entre 4 e 4,5 GiB;
- crítico: a partir de 4,5 GiB;
- limite técnico recomendado: 4,5 GiB.

O inventário e o dashboard aplicam esses limites automaticamente e bloqueiam o gate ao atingir 4,5 GiB.

## Recuperação

1. Abra o [Dashboard BACEN-04](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1162).
2. Localize o último `snapshot_id` saudável.
3. Restaure em diretório isolado.
4. Valide `PRAGMA quick_check`, SHA-256 e contagens.
5. Não sobrescreva o banco original antes da aprovação.

## Segurança

- bucket privado e credencial restrita ao bucket;
- criptografia Restic antes do upload;
- dumps e restaurações removidos do runner;
- artifacts somente com evidências sanitizadas;
- logs sem secrets, conteúdo do banco ou URLs assinadas;
- rotação de credenciais após incidente;
- `production_touched=false` até aprovação governada.
