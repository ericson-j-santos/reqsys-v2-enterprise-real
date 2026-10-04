-- #2861 · Migração rotina de e-mail Prospecção Movimento — Portabilidade Consignado
-- View: vw_prospeccao_movimento_pendencias_observacao  (dataset "Pendências de observação/tratamento")
-- Versão: V1
--
-- Idempotente (CREATE OR ALTER) — ver V1__vw_prospeccao_movimento_fechamento_diario.sql
-- para as notas gerais de idempotência e o GAP #2861-1 (schema real ainda não
-- confirmado). Stub válido, 0 linhas, mesmo contrato de colunas que
-- backend/app/services/movimento_email/models.py (ItemPendenciaObservacao) espera.

CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_observacao
AS
    -- Exemplo de extração real (ajustar tabela/coluna reais e remover o
    -- "WHERE 1 = 0" do stub abaixo assim que confirmado com a equipe de dados):
    --
    -- SELECT
    --     o.protocolo,
    --     o.tipo_inconsistencia,
    --     o.descricao,
    --     o.etapa,
    --     o.data_referencia
    -- FROM dbo.MovimentoPendenciasObservacao AS o

    SELECT
        CAST(NULL AS VARCHAR(50))  AS protocolo,
        CAST(NULL AS VARCHAR(120)) AS tipo_inconsistencia,
        CAST(NULL AS VARCHAR(500)) AS descricao,
        CAST(NULL AS VARCHAR(120)) AS etapa,
        CAST(NULL AS DATE)         AS data_referencia
    WHERE 1 = 0;
