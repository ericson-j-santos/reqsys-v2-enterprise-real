# Runbook — Corte de SQLite para Postgres em hml/prod (Fly.io)

Ver [ADR-043](../ADR/ADR-043-backup-rotacao-retencao.md) para o racional (centralizar o mesmo engine — Postgres — em todos os ambientes).

## Por que isso é um passo manual, não um PR automático

`fly.toml`, `backend/fly.staging.toml` e `backend/fly.dev.toml` hoje apontam para
`sqlite:////data/reqsys.db` em volumes Fly (`reqsys_data`, `reqsys_data_stg`,
`reqsys_data_dev`) que **muito provavelmente têm dados reais** (os hostnames
`reqsys-api.fly.dev`, `reqsys-app.fly.dev` etc. sugerem apps já implantados e em uso).

Trocar `DATABASE_URL` nesses arquivos sem:
1. provisionar um Postgres real acessível a partir do Fly, e
2. migrar os dados existentes do SQLite para lá,

...faria a próxima implantação subir com um banco **vazio** — perda de dados
efetiva, mesmo que o volume antigo continue existindo (só deixaria de ser usado).
Por isso este corte é documentado aqui como procedimento manual, não aplicado
automaticamente nos arquivos `fly*.toml`.

## Pré-requisitos

- Acesso `flyctl` autenticado (`fly auth whoami`) com permissão nos apps
  `reqsys-api-dev`, `reqsys-api-stg`, `reqsys-api` (prod).
- Backup do SQLite atual de cada ambiente (passo 1).
- Uma janela de manutenção — o app fica indisponível durante o corte de cada ambiente.

## Procedimento (repetir por ambiente: dev → staging → prod, nessa ordem)

### 1. Backup do SQLite atual do volume Fly

```bash
fly ssh sftp get /data/reqsys.db ./reqsys-<ambiente>-backup-$(date +%Y%m%d).db -a reqsys-api-dev
```

### 2. Provisionar o Postgres

Opção A — Fly Postgres gerenciado:
```bash
fly postgres create --name reqsys-db-dev --region gru --vm-size shared-cpu-1x
fly postgres attach reqsys-db-dev -a reqsys-api-dev   # gera e seta DATABASE_URL como secret automaticamente
```

Opção B — Postgres gerenciado externo (RDS, Neon, Supabase etc.): criar a instância
e obter a connection string manualmente.

### 3. Aplicar o schema no Postgres novo

```bash
# a partir de backend/, com DATABASE_URL apontando pro Postgres novo (nao pro fly.toml)
DATABASE_URL="postgresql+psycopg2://..." python -m alembic upgrade head
# se `alembic upgrade head` nao criar nada (baseline vazio — ver ADR-042), rode a app uma vez
# localmente contra essa URL para o create_all() de app/main.py criar o schema, depois
# `alembic stamp head`.
```

### 4. Migrar os dados do backup SQLite para o Postgres novo

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-url sqlite:///./reqsys-<ambiente>-backup-YYYYMMDD.db \
  --postgres-url postgresql+psycopg2://... \
  --dry-run   # confira as contagens por tabela antes de rodar de verdade

python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-url sqlite:///./reqsys-<ambiente>-backup-YYYYMMDD.db \
  --postgres-url postgresql+psycopg2://...
```

### 5. Setar o secret e trocar o DATABASE_URL do `fly.toml`

**Nunca** coloque a connection string com senha direto no `[env]` do `fly.toml`
(seria segredo hardcoded versionado — ADR-002/ADR-005). Use `fly secrets`:

```bash
fly secrets set DATABASE_URL="postgresql+psycopg2://..." -a reqsys-api-dev
```

Se `fly postgres attach` (passo 2, opção A) já foi usado, o secret já está setado —
só remova a linha `DATABASE_URL = "sqlite:////data/reqsys.db"` do `[env]` do
`fly.toml` correspondente (o secret sobrepõe `[env]` em runtime).

### 6. Deploy e validação

```bash
fly deploy -a reqsys-api-dev -c backend/fly.dev.toml
fly logs -a reqsys-api-dev
curl https://reqsys-api-dev.fly.dev/api/runtime/health
curl https://reqsys-api-dev.fly.dev/api/runtime/readiness
```

Confirme no log a linha `database_startup_probe_ok` (ver `app/main.py`) e teste
login + listagem de requisitos manualmente antes de considerar o corte concluído.

### 7. Rollback

Não apague o volume `reqsys_data*` nem o secret antigo — se o Postgres apresentar
problema, reverta removendo o secret `DATABASE_URL` (`fly secrets unset
DATABASE_URL -a <app>`) para o app voltar a usar o `[env]` com SQLite, e faça
`fly deploy` novamente. Só descomissione o volume SQLite após um período de
estabilidade confirmado no Postgres (sugestão: 30 dias).

## Ordem recomendada

1. `reqsys-api-dev` (menor risco, sem usuários reais dependendo)
2. `reqsys-api-stg` (validação completa antes de prod)
3. `reqsys-api` (prod) — só depois de staging estável por pelo menos alguns dias
