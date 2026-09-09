from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

import app.services.vba_office_container as container
from app.services.vba_office_container import OfficeVbaContainerError, analyze_office_vba_container


def _office_zip(project: bytes = b'fake-vba-project', path: str = 'xl/vbaProject.bin') -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr(path, project)
    return buffer.getvalue()


class FakeParser:
    def __init__(self, modules):
        self.modules = modules
        self.closed = False

    def detect_vba_macros(self):
        return bool(self.modules)

    def extract_macros(self):
        return iter(self.modules)

    def close(self):
        self.closed = True


def test_xlsm_extrai_modulos_sem_executar_office(monkeypatch):
    parser = FakeParser(
        [
            (
                'xl/vbaProject.bin',
                'VBA/modPedidos',
                'modPedidos.bas',
                b'Attribute VB_Name = "modPedidos"\nSub X()\nIf A = 1 Then B = 2\nEnd Sub',
            )
        ]
    )
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)

    resultado = analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert resultado['execution_performed'] is False
    assert resultado['source_persisted'] is False
    assert resultado['container']['vba_project_path'] == 'xl/vbaProject.bin'
    assert resultado['summary']['modules'] == 1
    assert resultado['summary']['business_rules'] == 1
    assert resultado['summary']['requirement_candidates'] == 1
    assert resultado['modules'][0]['name'] == 'modPedidos.bas'
    assert 'source' not in resultado['modules'][0]
    assert parser.closed is True


def test_docm_exige_vba_project_no_caminho_word(monkeypatch):
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: FakeParser([]))

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(
            _office_zip(path='xl/vbaProject.bin'),
            file_name='legado.docm',
        )

    assert exc_info.value.code == 'VBA_PROJECT_NOT_FOUND'
    assert exc_info.value.context['expected_path'] == 'word/vbaProject.bin'


def test_zip_com_path_traversal_e_rejeitado():
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('../vbaProject.bin', b'fake')

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(buffer.getvalue(), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_OFFICE_ARCHIVE_UNSAFE_PATH'


def test_sem_macro_retorna_erro_governado(monkeypatch):
    parser = FakeParser([])
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='sem-macro.xlsm')

    assert exc_info.value.code == 'VBA_MACROS_NOT_FOUND'
    assert parser.closed is True


def test_falha_interna_do_parser_nao_vaza_detalhe(monkeypatch):
    class ParserFalho(FakeParser):
        def detect_vba_macros(self):
            raise RuntimeError('segredo interno que nao pode vazar')

    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: ParserFalho([]))

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='falha.xlsm')

    assert exc_info.value.code == 'VBA_PROJECT_PARSE_FAILED'
    assert exc_info.value.context == {'parser_error_type': 'RuntimeError'}
    assert 'segredo interno' not in str(exc_info.value.context)
