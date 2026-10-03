-- TODO(#2861): confirmar view real do dataset "Pendências de observação/tratamento"
-- (inconsistências agrupadas encontradas durante o processamento).
-- Ver docs/architecture/movimento-email-pipeline.md (gap #1).
SELECT
    protocolo,
    tipo_inconsistencia,
    descricao,
    etapa
FROM vw_prospeccao_movimento_pendencias_observacao
WHERE data_referencia = ?
ORDER BY tipo_inconsistencia;
