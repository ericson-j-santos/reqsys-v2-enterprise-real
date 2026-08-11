-- #2861 · Migração rotina de e-mail Prospecção Movimento — Portabilidade Consignado
-- View: vw_prospeccao_movimento_pendencias_historicas  (dataset "Pendências históricas")
-- Versão: V1
--
-- Idempotente (CREATE OR ALTER) — ver V1__vw_prospeccao_movimento_fechamento_diario.sql
-- para as notas gerais de idempotência e o GAP #2861-1 (schema real ainda não
-- confirmado). Stub válido, 0 linhas, mesmo contrato de colunas que
-- backend/app/services/movimento_email/models.py (ItemPendenciaHistorica) espera.

CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_historicas
AS
    -- Exemplo de extração real (ajustar tabela/coluna reais e remover o
    -- "WHERE 1 = 0" do stub abaixo assim que confirmado com a equipe de dados):
    --
    -- SELECT
    --     h.periodo_referencia,
    --     h.pendencia,
    --     h.quantidade,
    --     h.percentual,
    --     h.data_referencia
    -- FROM dbo.MovimentoPendenciasHistorico AS h

    SELECT
        CAST(NULL AS VARCHAR(20))  AS periodo_referencia,
        CAST(NULL AS VARCHAR(200)) AS pendencia,
        CAST(NULL AS INT)          AS quantidade,
        CAST(NULL AS DECIMAL(5, 2)) AS percentual,
        CAST(NULL AS DATE)         AS data_referencia
    WHERE 1 = 0;
