from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

import app.api.vba_legacy as vba_api
from app.api.vba_legacy import analyze_vba_upload, vba_analyzer_readiness


def _arquivo(nome: str, conteudo: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(conteudo),
        filename=nome,
        headers=Headers({'content-type': 'application/octet-stream'}),
    )


def _xlsm_fake() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('xl/vbaProject.bin', b'fake')
    return buffer.getvalue()


async def test_upload_vba_retorna_envelope_com_correlation_id_e_sem_persistir_fonte():
    resposta = await analyze_vba_upload(
        arquivo=_arquivo('modTeste.bas', b'Sub X()\nIf A = 1 Then B = 2\nEnd Sub'),
        user={'papel': 'admin'},
        x_correlation_id='corr-vba-001',
    )

    assert resposta['success'] is True
    assert resposta['meta']['correlation_id'] == 'corr-vba-001'
    assert resposta['meta']['idempotent_analysis'] is True
    assert resposta['meta']['source_persisted'] is False
    assert resposta['meta']['execution_performed'] is False
    assert resposta['data']['analysis_type'] == 'static_only'
    assert resposta['data']['execution_performed'] is False
    assert resposta['data']['summary']['requirement_candidates'] == 1


async def test_upload_cp1252_e_aceito():
    conteudo = 'Sub X()\nIf situação = "PENDENTE" Then ação = "ANALISAR"\nEnd Sub'.encode('cp1252')

    resposta = await analyze_vba_upload(
        arquivo=_arquivo('acentos.bas', conteudo),
        user={'papel': 'admin'},
        x_correlation_id=None,
    )

    assert resposta['success'] is True
    assert resposta['data']['summary']['business_rules'] == 1


async def test_conteiner_xlsm_usa_extracao_estatica(monkeypatch):
    def fake_analyze(content: bytes, *, file_name: str):
        assert content.startswith(b'PK')
        assert file_name == 'legado.xlsm'
        return {
            'analysis_type': 'static_only',
            'execution_performed': False,
            'source_persisted': False,
            'summary': {'modules': 2},
        }

    monkeypatch.setattr(vba_api, 'analyze_office_vba_container', fake_analyze)

    resposta = await analyze_vba_upload(
        arquivo=_arquivo('legado.xlsm', _xlsm_fake()),
        user={'papel': 'admin'},
        x_correlation_id='corr-xlsm-001',
    )

    assert resposta['success'] is True
    assert resposta['meta']['correlation_id'] == 'corr-xlsm-001'
    assert resposta['data']['summary']['modules'] == 2
    assert resposta['data']['execution_performed'] is False


async def test_erro_governado_do_conteiner_e_convertido_para_http(monkeypatch):
    def fake_analyze(content: bytes, *, file_name: str):
        raise vba_api.OfficeVbaContainerError(
            'VBA_PROJECT_NOT_FOUND',
            422,
            {'expected_path': 'xl/vbaProject.bin'},
        )

    monkeypatch.setattr(vba_api, 'analyze_office_vba_container', fake_analyze)

    with pytest.raises(HTTPException) as exc_info:
        await analyze_vba_upload(
            arquivo=_arquivo('legado.xlsm', _xlsm_fake()),
            user={'papel': 'admin'},
            x_correlation_id=None,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        'code': 'VBA_PROJECT_NOT_FOUND',
        'expected_path': 'xl/vbaProject.bin',
    }


async def test_limite_de_upload_de_fonte_e_configuravel_por_ambiente(monkeypatch):
    monkeypatch.setenv('VBA_ANALYZER_MAX_UPLOAD_BYTES', '10')

    with pytest.raises(HTTPException) as exc_info:
        await analyze_vba_upload(
            arquivo=_arquivo('grande.bas', b'01234567890'),
            user={'papel': 'admin'},
            x_correlation_id=None,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail['code'] == 'VBA_INPUT_TOO_LARGE'
    assert exc_info.value.detail['input_kind'] == 'source'


async def test_limite_de_upload_de_conteiner_e_independente(monkeypatch):
    monkeypatch.setenv('VBA_ANALYZER_MAX_CONTAINER_BYTES', '10')

    with pytest.raises(HTTPException) as exc_info:
        await analyze_vba_upload(
            arquivo=_arquivo('grande.xlsm', b'01234567890'),
            user={'papel': 'admin'},
            x_correlation_id=None,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail['input_kind'] == 'office_container'


def test_readiness_expõe_estado_do_parser_office(monkeypatch):
    monkeypatch.setattr(
        vba_api,
        'office_container_readiness',
        lambda: {
            'ready': True,
            'dependency': 'oletools',
            'version': '0.60.2',
            'mode': 'vba_project_only',
            'office_execution': False,
        },
    )

    resposta = vba_analyzer_readiness(user={'papel': 'admin'})

    assert resposta['success'] is True
    assert resposta['data']['ready'] is True
    assert resposta['data']['analysis_type'] == 'static_only'
    assert resposta['data']['execution_performed'] is False
    assert resposta['data']['office_container_ready'] is True
    assert '.xlsm' in resposta['data']['supported_office_extensions']
