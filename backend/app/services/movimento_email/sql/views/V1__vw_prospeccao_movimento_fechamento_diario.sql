-- #2861 · Migração rotina de e-mail Prospecção Movimento — Portabilidade Consignado
-- View: vw_prospeccao_movimento_fechamento_diario  (dataset "Fechamento diário")
-- Versão: V1
--
-- Idempotente: CREATE OR ALTER falha e recria de novo produz sempre o mesmo
-- estado, seguro para rodar quantas vezes for preciso (SQL Server 2016 SP1+
-- e Azure SQL Database — se o ambiente for mais antigo, ver README.md nesta
-- pasta para a variante IF OBJECT_ID(...) IS NULL).
--
-- GAP #2861-1 (ver docs/architecture/movimento-email-pipeline.md): o schema
-- real das tabelas de origem do SSRS legado ainda não foi confirmado com a
-- equipe de dados. Este script cria a view com o CONTRATO exato que
-- backend/app/services/movimento_email/repository.py e models.py esperam —
-- deployável e idempotente hoje, mas retornando 0 linhas (stub) até alguém
-- com acesso ao schema legado substituir o corpo pelo SELECT real comentado
-- abaixo como exemplo.
--
-- NÃO altere nomes/tipos de coluna aqui sem também atualizar
-- backend/app/services/movimento_email/models.py e repository.py.

CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_fechamento_diario
AS
    -- Exemplo de como a extração real provavelmente ficará — ajustar nomes
    -- de tabela/coluna reais assim que confirmados com a equipe de dados,
    -- e então remover o "WHERE 1 = 0" do stub abaixo:
    --
    -- SELECT
    --     f.indicador,
    --     CAST(f.valor AS VARCHAR(100)) AS valor,
    --     f.observacao,
    --     f.data_referencia
    -- FROM dbo.MovimentoFechamentoDiario AS f

    SELECT
        CAST(NULL AS VARCHAR(200)) AS indicador,
        CAST(NULL AS VARCHAR(100)) AS valor,
        CAST(NULL AS VARCHAR(500)) AS observacao,
        CAST(NULL AS DATE)         AS data_referencia
    WHERE 1 = 0;
