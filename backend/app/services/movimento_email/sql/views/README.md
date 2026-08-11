# Views de origem — Movimento Email (#2861)

Artefato de banco **versionado e autocontido** (ADR-012) para o SQL Server de
origem consumido pela rotina de e-mail Prospecção Movimento — Portabilidade
Consignado. Autocontido = só T-SQL puro, sem dependência de nenhuma
ferramenta externa (nada de Flyway/Liquibase); aplicado por
`scripts/aplicar_movimento_email_views.py` usando só `pyodbc` (já é
dependência do projeto).

## Convenção de versionamento

- Cada versão é um prefixo `V<N>__` nos nomes de arquivo (`V1__...sql`, uma
  vez publicada uma versão **nunca é editada** — mudanças viram `V2__...`).
- `MANIFEST.json` registra o SHA-256 de cada arquivo de cada versão. O
  runner recalcula o hash antes de aplicar e recusa rodar se divergir do
  manifesto — protege contra edição silenciosa de uma versão já "fechada".
- `V<N>__rollback.sql` desfaz a versão `V<N>` inteira (idempotente: `DROP
  VIEW IF EXISTS`, seguro mesmo se já não existir).

## Idempotência

Todas as views usam `CREATE OR ALTER VIEW` — rodar o mesmo arquivo 1x ou
50x produz sempre o mesmo estado final, sem erro. Requer SQL Server 2016
SP1+ ou Azure SQL Database. Se o ambiente de origem for mais antigo,
troque o cabeçalho de cada arquivo pelo padrão clássico:

```sql
IF OBJECT_ID('dbo.vw_...', 'V') IS NULL
    EXEC('CREATE VIEW dbo.vw_... AS SELECT 1 AS placeholder');
GO
ALTER VIEW dbo.vw_...
AS
    ...
GO
```

## Estado atual (V1) — stub de contrato, não a extração real

**Gap #2861-1** (ver `docs/architecture/movimento-email-pipeline.md`): a
equipe de dados ainda não confirmou o schema real das tabelas legadas do
SSRS. `V1` cria as 4 views com o contrato de colunas exato que
`backend/app/services/movimento_email/repository.py`/`models.py` esperam,
mas o corpo é `SELECT ... WHERE 1 = 0` (compila, é deployável e idempotente
hoje, mas sempre retorna 0 linhas). Cada arquivo tem, comentado, um exemplo
de como o `SELECT` real provavelmente ficará — a equipe de dados só precisa
descomentar/ajustar os nomes de tabela/coluna reais e remover o `WHERE 1 =
0`, sem precisar tocar em versionamento, idempotência ou no runner.

## Como aplicar

```powershell
cd backend
python ..\scripts\aplicar_movimento_email_views.py status                # valida checksums locais contra MANIFEST.json
python ..\scripts\aplicar_movimento_email_views.py aplicar --dry-run     # mostra o plano, não conecta em nada
python ..\scripts\aplicar_movimento_email_views.py aplicar               # aplica de verdade (exige MOVIMENTO_EMAIL_SOURCE_DSN)
python ..\scripts\verificar_movimento_email_fontes.py verificar          # confirma ao vivo que as 4 views existem com as colunas certas
```

Rollback (destrutivo — remove as views; exige confirmação explícita):

```powershell
python ..\scripts\aplicar_movimento_email_views.py rollback --confirmar
```
