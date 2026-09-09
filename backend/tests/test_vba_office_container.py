from importlib.metadata import PackageNotFoundError
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
    def __init__(self, modules, *, stomping=False, stomping_error=None):
        self.modules = modules
        self.stomping = stomping
        self.stomping_error = stomping_error
        self.closed = False

    def detect_vba_macros(self):
        return bool(self.modules)

    def extract_macros(self):
        return iter(self.modules)

    def detect_vba_stomping(self):
        if self.stomping_error is not None:
            raise self.stomping_error
        return self.stomping

    def close(self):
        self.closed = True


def _module(name: str = 'modTeste.bas', source: object = b'Sub X()\nEnd Sub'):
    return ('xl/vbaProject.bin', f'VBA/{name}', name, source)


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
    assert resultado['summary']['vba_stomping_status'] == 'not_detected'
    assert resultado['integrity']['status'] == 'NO_INDICATION'
    assert resultado['integrity']['source_vs_pcode_checked'] is True
    assert resultado['modules'][0]['name'] == 'modPedidos.bas'
    assert 'source' not in resultado['modules'][0]
    assert parser.closed is True


def test_detecta_vba_stomping_e_exige_revisao(monkeypatch):
    parser = FakeParser([_module()], stomping=True)
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)

    resultado = analyze_office_vba_container(_office_zip(), file_name='stomped.xlsm')

    assert resultado['integrity']['status'] == 'REVIEW_REQUIRED'
    assert resultado['integrity']['vba_stomping']['detected'] is True
    assert resultado['summary']['vba_stomping_status'] == 'detected'
    assert resultado['summary']['risks_by_severity']['high'] == 1
    assert any(risk['code'] == 'VBA_STOMPING_DETECTED' for risk in resultado['risks'])
    assert resultado['modernization_plan'][0]['required'] is True


def test_falha_na_comparacao_pcode_fica_inconclusiva_sem_vazar_erro(monkeypatch):
    parser = FakeParser([_module()], stomping_error=RuntimeError('segredo do parser'))
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)

    resultado = analyze_office_vba_container(_office_zip(), file_name='inconclusivo.xlsm')

    stomping = resultado['integrity']['vba_stomping']
    assert resultado['integrity']['status'] == 'INDETERMINATE'
    assert resultado['integrity']['source_vs_pcode_checked'] is False
    assert stomping['status'] == 'indeterminate'
    assert stomping['detected'] is None
    assert stomping['parser_error_type'] == 'RuntimeError'
    assert 'segredo do parser' not in str(stomping)
    assert any(
        risk['code'] == 'VBA_STOMPING_ASSESSMENT_INDETERMINATE'
        for risk in resultado['risks']
    )
    assert resultado['modernization_plan'][0]['required'] is True


def test_parser_sem_metodo_de_stomping_nao_e_tratado_como_limpo(monkeypatch):
    class ParserLegado:
        def detect_vba_macros(self):
            return True

        def extract_macros(self):
            return iter([_module()])

        def close(self):
            pass

    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: ParserLegado())

    resultado = analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert resultado['integrity']['status'] == 'INDETERMINATE'
    assert resultado['integrity']['vba_stomping']['reason'] == 'parser_method_unavailable'
    assert resultado['summary']['risks_by_severity']['medium'] == 1


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


def test_readiness_reporta_parser_instalado(monkeypatch):
    monkeypatch.setattr(container.importlib.metadata, 'version', lambda name: '0.60.2')

    assert container.office_container_readiness() == {
        'ready': True,
        'dependency': 'oletools',
        'version': '0.60.2',
        'mode': 'vba_project_only',
        'office_execution': False,
        'pcode_integrity_check': True,
        'pcode_engine': 'pcodedmp',
    }


def test_readiness_reporta_parser_ausente(monkeypatch):
    def missing(_name):
        raise PackageNotFoundError

    monkeypatch.setattr(container.importlib.metadata, 'version', missing)

    resultado = container.office_container_readiness()

    assert resultado['ready'] is False
    assert resultado['version'] is None
    assert resultado['pcode_integrity_check'] is False


def test_extensao_office_invalida_e_rejeitada():
    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='legado.xlsx')

    assert exc_info.value.code == 'VBA_OFFICE_EXTENSION_UNSUPPORTED'


def test_zip_invalido_e_rejeitado():
    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(b'nao-e-zip', file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_OFFICE_INVALID_ZIP'


def test_limite_de_itens_do_zip_e_aplicado(monkeypatch):
    monkeypatch.setattr(container, 'MAX_ARCHIVE_ENTRIES', 1)

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_OFFICE_TOO_MANY_ARCHIVE_ENTRIES'
    assert exc_info.value.status_code == 413


def test_limite_descompactado_e_aplicado(monkeypatch):
    monkeypatch.setattr(container, 'MAX_ARCHIVE_UNCOMPRESSED_BYTES', 1)

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_OFFICE_ARCHIVE_TOO_LARGE_AFTER_DECOMPRESSION'


def test_razao_de_compactacao_suspeita_e_bloqueada(monkeypatch):
    monkeypatch.setattr(container, 'MAX_COMPRESSION_RATIO', 1.0)
    project = b'A' * 1_048_577

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(project=project), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_OFFICE_SUSPICIOUS_COMPRESSION_RATIO'


def test_limite_do_vba_project_e_aplicado(monkeypatch):
    monkeypatch.setattr(container, 'MAX_PROJECT_BYTES', 2)

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(project=b'abc'), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_PROJECT_TOO_LARGE'


def test_vba_project_vazio_e_rejeitado():
    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(project=b''), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_PROJECT_EMPTY'


def test_limite_de_modulos_e_aplicado(monkeypatch):
    parser = FakeParser([_module('a.bas'), _module('b.bas')])
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)
    monkeypatch.setattr(container, 'MAX_MODULES', 1)

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_TOO_MANY_MODULES'
    assert parser.closed is True


def test_limite_de_expansao_da_fonte_e_aplicado(monkeypatch):
    parser = FakeParser([_module(source=b'abcd')])
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)
    monkeypatch.setattr(container, 'MAX_TOTAL_VBA_SOURCE_CHARS', 3)

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_SOURCE_EXPANSION_TOO_LARGE'


def test_tipo_de_fonte_invalido_e_rejeitado(monkeypatch):
    parser = FakeParser([_module(source=object())])
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)

    with pytest.raises(OfficeVbaContainerError) as exc_info:
        analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert exc_info.value.code == 'VBA_MODULE_SOURCE_ENCODING_UNSUPPORTED'


def test_agrega_riscos_por_severidade_e_modulo(monkeypatch):
    parser = FakeParser([_module()])
    monkeypatch.setattr(container, '_parser_factory', lambda file_name, data: parser)

    def fake_analysis(_source, *, file_name):
        return {
            'sha256': 'a' * 64,
            'summary': {
                'procedures': 1,
                'dependencies': 0,
                'business_rules': 0,
                'requirement_candidates': 1,
            },
            'module': {'name': file_name},
            'procedures': [{'name': 'X'}],
            'dependencies': [],
            'business_rules': [],
            'risks': [
                {'code': 'VBA004', 'severity': 'critical'},
                {'code': 'VBA999', 'severity': 'unknown'},
            ],
            'requirement_candidates': [{'id': 'REQ-VBA-1'}],
        }

    monkeypatch.setattr(container, 'analyze_vba_source', fake_analysis)

    resultado = analyze_office_vba_container(_office_zip(), file_name='legado.xlsm')

    assert resultado['summary']['risks_by_severity']['critical'] == 1
    assert resultado['risks'][0]['module'] == 'modTeste.bas'
    assert resultado['requirement_candidates'][0]['module'] == 'modTeste.bas'
    assert resultado['modernization_plan'][1]['required'] is True
    assert resultado['modernization_plan'][2]['required'] is True
