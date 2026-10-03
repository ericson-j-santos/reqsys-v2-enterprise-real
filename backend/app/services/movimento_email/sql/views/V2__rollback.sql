-- Rollback V2: restaura o contrato V1 (stub de 0 linhas).
CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_fechamento_diario
AS
SELECT
    CAST(NULL AS VARCHAR(200)) AS indicador,
    CAST(NULL AS VARCHAR(100)) AS valor,
    CAST(NULL AS VARCHAR(500)) AS observacao,
    CAST(NULL AS DATE) AS data_referencia
WHERE 1 = 0;

CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_cadastro
AS
SELECT
    CAST(NULL AS VARCHAR(50)) AS protocolo,
    CAST(NULL AS VARCHAR(200)) AS cliente,
    CAST(NULL AS VARCHAR(11)) AS cpf,
    CAST(NULL AS VARCHAR(200)) AS pendencia,
    CAST(NULL AS INT) AS dias_em_aberto,
    CAST(NULL AS VARCHAR(120)) AS responsavel,
    CAST(NULL AS DATE) AS data_referencia
WHERE 1 = 0;

CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_historicas
AS
SELECT
    CAST(NULL AS VARCHAR(20)) AS periodo_referencia,
    CAST(NULL AS VARCHAR(200)) AS pendencia,
    CAST(NULL AS INT) AS quantidade,
    CAST(NULL AS DECIMAL(5,2)) AS percentual,
    CAST(NULL AS DATE) AS data_referencia
WHERE 1 = 0;

CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_observacao
AS
SELECT
    CAST(NULL AS VARCHAR(50)) AS protocolo,
    CAST(NULL AS VARCHAR(120)) AS tipo_inconsistencia,
    CAST(NULL AS VARCHAR(500)) AS descricao,
    CAST(NULL AS VARCHAR(120)) AS etapa,
    CAST(NULL AS DATE) AS data_referencia
WHERE 1 = 0;
