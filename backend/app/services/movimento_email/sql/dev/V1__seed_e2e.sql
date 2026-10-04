-- Dados exclusivamente sintéticos para DEV/E2E.
-- O marcador permite repetição idempotente sem misturar dados externos.

DECLARE @source_tag VARCHAR(120) = 'REQSYS_V2_E2E';
DECLARE @data_referencia DATE = '2099-12-31';

DELETE FROM movimento_src.fechamento_diario WHERE source_tag = @source_tag;
DELETE FROM movimento_src.pendencias_cadastro WHERE source_tag = @source_tag;
DELETE FROM movimento_src.pendencias_historicas WHERE source_tag = @source_tag;
DELETE FROM movimento_src.pendencias_observacao WHERE source_tag = @source_tag;

INSERT INTO movimento_src.fechamento_diario
    (indicador, valor, observacao, data_referencia, source_tag)
VALUES
    ('E2E_QTD', '12', 'marcador controlado', @data_referencia, @source_tag),
    ('E2E_VALOR', '345.67', 'segunda linha', @data_referencia, @source_tag);

INSERT INTO movimento_src.pendencias_cadastro
    (protocolo, cliente, cpf, pendencia, dias_em_aberto, responsavel, data_referencia, source_tag)
VALUES
    ('E2E-001', 'CLIENTE DEMO', '00000000000', 'DOCUMENTO', 3, 'REQSYS-E2E', @data_referencia, @source_tag);

INSERT INTO movimento_src.pendencias_historicas
    (periodo_referencia, pendencia, quantidade, percentual, data_referencia, source_tag)
VALUES
    ('2099-12', 'DOCUMENTO', 1, 100.00, @data_referencia, @source_tag);

INSERT INTO movimento_src.pendencias_observacao
    (protocolo, tipo_inconsistencia, descricao, etapa, data_referencia, source_tag)
VALUES
    ('E2E-001', 'VALIDACAO', 'registro sintético controlado', 'E2E', @data_referencia, @source_tag);
