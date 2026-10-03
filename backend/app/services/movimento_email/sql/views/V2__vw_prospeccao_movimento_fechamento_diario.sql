-- V2: implementação real sobre a camada-fonte canônica movimento_src.
CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_fechamento_diario
AS
SELECT
    indicador,
    valor,
    observacao,
    data_referencia
FROM movimento_src.fechamento_diario;
