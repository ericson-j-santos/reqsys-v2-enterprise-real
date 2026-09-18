-- V2: implementação real sobre a camada-fonte canônica movimento_src.
CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_historicas
AS
SELECT
    periodo_referencia,
    pendencia,
    quantidade,
    percentual,
    data_referencia
FROM movimento_src.pendencias_historicas;
