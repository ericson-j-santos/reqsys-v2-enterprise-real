-- V2: implementação real sobre a camada-fonte canônica movimento_src.
CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_cadastro
AS
SELECT
    protocolo,
    cliente,
    cpf,
    pendencia,
    dias_em_aberto,
    responsavel,
    data_referencia
FROM movimento_src.pendencias_cadastro;
