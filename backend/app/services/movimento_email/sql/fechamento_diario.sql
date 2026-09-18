-- TODO(#2861): confirmar com a equipe de dados o nome real da view/tabela que
-- hoje alimenta o dataset "Fechamento diário" no relatório SSRS legado.
-- Nome abaixo é um placeholder de convenção (vw_<dominio>_<dataset>) até a
-- confirmação — ver docs/architecture/movimento-email-pipeline.md (gap #1).
SELECT
    indicador,
    valor,
    observacao
FROM vw_prospeccao_movimento_fechamento_diario
WHERE data_referencia = ?
ORDER BY indicador;
