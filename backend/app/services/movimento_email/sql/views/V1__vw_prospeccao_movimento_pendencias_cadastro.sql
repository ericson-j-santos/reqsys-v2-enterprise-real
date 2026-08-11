-- #2861 · Migração rotina de e-mail Prospecção Movimento — Portabilidade Consignado
-- View: vw_prospeccao_movimento_pendencias_cadastro  (dataset "Pendências de cadastramento")
-- Versão: V1
--
-- Idempotente (CREATE OR ALTER) — ver V1__vw_prospeccao_movimento_fechamento_diario.sql
-- para as notas gerais de idempotência e o GAP #2861-1 (schema real ainda não
-- confirmado). Stub válido, 0 linhas, mesmo contrato de colunas que
-- backend/app/services/movimento_email/models.py (ItemPendenciaCadastro) espera.

CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_cadastro
AS
    -- Exemplo de extração real (ajustar tabela/coluna reais e remover o
    -- "WHERE 1 = 0" do stub abaixo assim que confirmado com a equipe de dados):
    --
    -- SELECT
    --     p.protocolo,
    --     p.cliente,
    --     p.cpf,
    --     p.pendencia,
    --     p.dias_em_aberto,
    --     p.responsavel,
    --     p.data_referencia
    -- FROM dbo.MovimentoPendenciasCadastro AS p
    -- WHERE p.status_operacional = 'CONCLUIDO'
    --   AND p.status_cadastral <> 'REGULAR'

    SELECT
        CAST(NULL AS VARCHAR(50))  AS protocolo,
        CAST(NULL AS VARCHAR(200)) AS cliente,
        CAST(NULL AS VARCHAR(11))  AS cpf,
        CAST(NULL AS VARCHAR(200)) AS pendencia,
        CAST(NULL AS INT)          AS dias_em_aberto,
        CAST(NULL AS VARCHAR(120)) AS responsavel,
        CAST(NULL AS DATE)         AS data_referencia
    WHERE 1 = 0;
