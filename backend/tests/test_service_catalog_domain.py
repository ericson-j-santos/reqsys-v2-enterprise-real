from __future__ import annotations

import pytest

from app.domain.service_catalog import (
    CATALOG_SCHEMA_VERSION,
    MAX_FIELDS_PER_OFFERING,
    OfferingField,
    OfferingFieldSchema,
    OfferingFieldType,
    OfferingSubmissionError,
    normalize_offering_code,
)
from app.domain.service_management import ServiceManagementValidationError

SCHEMA_RAW = {
    'schema_version': CATALOG_SCHEMA_VERSION,
    'fields': [
        {'key': 'justificativa', 'label': 'Justificativa', 'type': 'STRING', 'required': True, 'max_length': 120},
        {'key': 'ambiente', 'label': 'Ambiente', 'type': 'ENUM', 'required': True, 'options': ['DEV', 'HML']},
        {'key': 'quantidade', 'label': 'Quantidade', 'type': 'INTEGER', 'min_value': 1, 'max_value': 10},
        {'key': 'urgente', 'label': 'Urgente', 'type': 'BOOLEAN'},
    ],
}


@pytest.fixture
def schema() -> OfferingFieldSchema:
    return OfferingFieldSchema.from_dict(SCHEMA_RAW)


def test_schema_roundtrip_preserva_contrato(schema: OfferingFieldSchema):
    assert schema.schema_version == CATALOG_SCHEMA_VERSION
    assert schema.keys == {'justificativa', 'ambiente', 'quantidade', 'urgente'}
    assert OfferingFieldSchema.from_dict(schema.to_dict()).to_dict() == schema.to_dict()


def test_submissao_valida_normaliza_e_descarta_opcionais_ausentes(schema: OfferingFieldSchema):
    resultado = schema.validate_submission(
        {'justificativa': '  acesso ao relatorio  ', 'ambiente': 'DEV', 'quantidade': 3}
    )
    assert resultado == {'justificativa': 'acesso ao relatorio', 'ambiente': 'DEV', 'quantidade': 3}


def test_submissao_vazia_em_schema_sem_campos_e_aceita():
    assert OfferingFieldSchema().validate_submission(None) == {}


def test_campo_obrigatorio_ausente_e_rejeitado(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='justificativa'):
        schema.validate_submission({'ambiente': 'DEV'})


def test_campo_obrigatorio_nulo_e_rejeitado(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='ambiente'):
        schema.validate_submission({'justificativa': 'ok', 'ambiente': None})


def test_campo_nao_declarado_e_rejeitado(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='nao_declarado|não declarados'):
        schema.validate_submission(
            {'justificativa': 'ok', 'ambiente': 'DEV', 'nao_declarado': 'x'}
        )


def test_enum_fora_das_options_e_rejeitado(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='ambiente'):
        schema.validate_submission({'justificativa': 'ok', 'ambiente': 'PROD'})


def test_string_acima_do_max_length_e_rejeitada(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='120 caracteres'):
        schema.validate_submission({'justificativa': 'x' * 121, 'ambiente': 'DEV'})


def test_string_vazia_e_rejeitada(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='justificativa'):
        schema.validate_submission({'justificativa': '   ', 'ambiente': 'DEV'})


@pytest.mark.parametrize('valor', ['3', 3.5, None.__class__, [3]])
def test_inteiro_sem_coercao_implicita(schema: OfferingFieldSchema, valor):
    with pytest.raises(OfferingSubmissionError, match='quantidade'):
        schema.validate_submission(
            {'justificativa': 'ok', 'ambiente': 'DEV', 'quantidade': valor}
        )


def test_boolean_nao_e_aceito_como_inteiro(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='quantidade'):
        schema.validate_submission(
            {'justificativa': 'ok', 'ambiente': 'DEV', 'quantidade': True}
        )


def test_inteiro_fora_dos_limites_e_rejeitado(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='>= 1'):
        schema.validate_submission(
            {'justificativa': 'ok', 'ambiente': 'DEV', 'quantidade': 0}
        )
    with pytest.raises(OfferingSubmissionError, match='<= 10'):
        schema.validate_submission(
            {'justificativa': 'ok', 'ambiente': 'DEV', 'quantidade': 11}
        )


def test_boolean_exige_booleano(schema: OfferingFieldSchema):
    with pytest.raises(OfferingSubmissionError, match='urgente'):
        schema.validate_submission(
            {'justificativa': 'ok', 'ambiente': 'DEV', 'urgente': 'sim'}
        )


def test_validacao_e_deterministica_para_a_mesma_entrada(schema: OfferingFieldSchema):
    entrada = {'justificativa': 'ok', 'ambiente': 'HML', 'quantidade': 2, 'urgente': False}
    assert schema.validate_submission(entrada) == schema.validate_submission(dict(entrada))


def test_enum_sem_options_e_rejeitado_no_contrato():
    with pytest.raises(ServiceManagementValidationError, match='exige options'):
        OfferingField(key='a', label='A', field_type=OfferingFieldType.ENUM)


def test_options_em_campo_nao_enum_e_rejeitado():
    with pytest.raises(ServiceManagementValidationError, match='somente|só se aplicam'):
        OfferingField(
            key='a', label='A', field_type=OfferingFieldType.STRING, options=('x',)
        )


def test_limites_em_campo_nao_inteiro_sao_rejeitados():
    with pytest.raises(ServiceManagementValidationError, match='min_value'):
        OfferingField(
            key='a', label='A', field_type=OfferingFieldType.STRING, min_value=1
        )


def test_key_invalida_e_rejeitada():
    with pytest.raises(ServiceManagementValidationError, match='key de campo'):
        OfferingField(key='Campo Invalido', label='A', field_type=OfferingFieldType.STRING)


def test_keys_duplicadas_sao_rejeitadas():
    campo = OfferingField(key='a', label='A', field_type=OfferingFieldType.STRING)
    with pytest.raises(ServiceManagementValidationError, match='duplicadas'):
        OfferingFieldSchema(fields=(campo, campo))


def test_limite_de_campos_por_oferta():
    campos = tuple(
        OfferingField(key=f'c{i}', label=f'C{i}', field_type=OfferingFieldType.STRING)
        for i in range(MAX_FIELDS_PER_OFFERING + 1)
    )
    with pytest.raises(ServiceManagementValidationError, match='excede'):
        OfferingFieldSchema(fields=campos)


def test_atributo_desconhecido_no_schema_e_rejeitado():
    with pytest.raises(ServiceManagementValidationError, match='não suportados'):
        OfferingFieldSchema.from_dict(
            {'fields': [{'key': 'a', 'label': 'A', 'type': 'STRING', 'extra': 1}]}
        )


def test_schema_version_divergente_e_rejeitado():
    with pytest.raises(ServiceManagementValidationError, match='schema_version'):
        OfferingFieldSchema.from_dict({'schema_version': '9.9.9', 'fields': []})


def test_normalize_offering_code():
    assert normalize_offering_code(' acesso-relatorio ') == 'ACESSO-RELATORIO'
    with pytest.raises(ServiceManagementValidationError):
        normalize_offering_code('')
    with pytest.raises(ServiceManagementValidationError):
        normalize_offering_code('codigo invalido')
