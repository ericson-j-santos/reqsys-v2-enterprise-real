-- V2: implementação real sobre a camada-fonte canônica movimento_src.
CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_observacao
AS
SELECT
    protocolo,
    tipo_inconsistencia,
    descricao,
    etapa,
    data_referencia
FROM movimento_src.pendencias_observacao;
