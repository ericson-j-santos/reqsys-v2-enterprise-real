-- TODO(#2861): confirmar view real do dataset "Pendências históricas"
-- (consolidado histórico de pendências por período).
-- Ver docs/architecture/movimento-email-pipeline.md (gap #1).
SELECT
    periodo_referencia,
    pendencia,
    quantidade,
    percentual
FROM vw_prospeccao_movimento_pendencias_historicas
WHERE data_referencia = ?
ORDER BY periodo_referencia DESC;
