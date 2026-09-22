-- TODO(#2861): confirmar view real do dataset "Pendências de cadastramento"
-- (registros concluídos operacionalmente mas com pendência cadastral aberta).
-- Ver docs/architecture/movimento-email-pipeline.md (gap #1).
SELECT
    protocolo,
    cliente,
    cpf,
    pendencia,
    dias_em_aberto,
    responsavel
FROM vw_prospeccao_movimento_pendencias_cadastro
WHERE data_referencia = ?
ORDER BY dias_em_aberto DESC;
