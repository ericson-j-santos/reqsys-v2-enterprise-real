import json

import pytest

from app.services.documento_demanda import (
    MAX_UPLOAD_BYTES,
    calcular_sha256,
    classificar_candidatos,
    extrair_texto_basico,
    serializar_candidatos,
    validar_upload,
)


def test_sha256_deterministico():
    conteudo = b'requisito governado'
    assert calcular_sha256(conteudo) == calcular_sha256(conteudo)


def test_upload_rejeita_tipo_nao_suportado():
    with pytest.raises(ValueError, match='tipo de arquivo não suportado'):
        validar_upload(nome_arquivo='arquivo.exe', content_type='application/octet-stream', conteudo=b'x')


def test_upload_rejeita_arquivo_vazio():
    with pytest.raises(ValueError, match='arquivo vazio'):
        validar_upload(nome_arquivo='arquivo.txt', content_type='text/plain', conteudo=b'')


def test_upload_rejeita_tamanho_acima_limite():
    with pytest.raises(ValueError, match='10 MB'):
        validar_upload(nome_arquivo='arquivo.txt', content_type='text/plain', conteudo=b'x' * (MAX_UPLOAD_BYTES + 1))


def test_classificacao_mantem_revisao_humana():
    texto = 'O sistema deve validar o CPF informado.\nSomente o gestor pode aprovar a solicitação.\nA consulta deve responder em até 5 segundos.'
    candidatos = classificar_candidatos(texto)
    assert len(candidatos) == 3
    assert all(item.requer_validacao_humana for item in candidatos)
    assert {item.tipo for item in candidatos} >= {'POSSIVEL_REQUISITO', 'POSSIVEL_REGRA_NEGOCIO'}


def test_documento_binario_nao_e_interpretado_sem_ocr():
    assert extrair_texto_basico('application/pdf', b'%PDF-falso') == ''


def test_serializacao_nao_cria_decisao_automatica():
    payload = json.loads(serializar_candidatos(classificar_candidatos('O sistema deve registrar auditoria.')))
    assert payload[0]['requer_validacao_humana'] is True
    assert 'aprovado' not in payload[0]
