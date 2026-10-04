from __future__ import annotations

import hashlib
import importlib.metadata
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from app.services.vba_semantic_analyzer import (
    analyze_vba_semantics as analyze_vba_source,
)

OFFICE_CONTAINER_EXTENSIONS = {'.xlsm', '.xlsb', '.xlam', '.docm', '.dotm'}
_EXPECTED_PROJECT_PATH = {
    '.xlsm': 'xl/vbaProject.bin',
    '.xlsb': 'xl/vbaProject.bin',
    '.xlam': 'xl/vbaProject.bin',
    '.docm': 'word/vbaProject.bin',
    '.dotm': 'word/vbaProject.bin',
}
MAX_ARCHIVE_ENTRIES = 2_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_PROJECT_BYTES = 8 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250.0
MAX_MODULES = 300
MAX_TOTAL_VBA_SOURCE_CHARS = 8 * 1024 * 1024


class OfficeVbaContainerError(Exception):
    def __init__(
        self,
        code: str,
        status_code: int = 422,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.context = context or {}


def _extension(file_name: str) -> str:
    lower = file_name.lower()
    for extension in OFFICE_CONTAINER_EXTENSIONS:
        if lower.endswith(extension):
            return extension
    return ''


def _safe_module_name(value: object) -> str:
    text = str(value or 'module.bas').replace('\\', '/')
    return text.rsplit('/', 1)[-1] or 'module.bas'


def _parser_factory(file_name: str, data: bytes):
    try:
        from oletools.olevba import VBA_Parser
    except ImportError as exc:
        raise OfficeVbaContainerError(
            'VBA_OFFICE_PARSER_UNAVAILABLE',
            503,
            {'dependency': 'oletools'},
        ) from exc
    return VBA_Parser(file_name, data=data)


def office_container_readiness() -> dict[str, object]:
    try:
        version = importlib.metadata.version('oletools')
    except importlib.metadata.PackageNotFoundError:
        return {
            'ready': False,
            'dependency': 'oletools',
            'version': None,
            'mode': 'vba_project_only',
            'office_execution': False,
            'pcode_integrity_check': False,
            'semantic_data_flow': True,
        }
    return {
        'ready': True,
        'dependency': 'oletools',
        'version': version,
        'mode': 'vba_project_only',
        'office_execution': False,
        'pcode_integrity_check': True,
        'pcode_engine': 'pcodedmp',
        'semantic_data_flow': True,
    }


def _validate_member_name(name: str) -> None:
    normalized = PurePosixPath(name.replace('\\', '/'))
    if normalized.is_absolute() or '..' in normalized.parts:
        raise OfficeVbaContainerError(
            'VBA_OFFICE_ARCHIVE_UNSAFE_PATH',
            422,
            {'member': _safe_module_name(name)},
        )


def _validate_archive_and_read_project(
    content: bytes,
    *,
    extension: str,
) -> tuple[bytes, str, dict[str, int | float]]:
    expected_path = _EXPECTED_PROJECT_PATH[extension]
    try:
        archive = ZipFile(BytesIO(content))
    except BadZipFile as exc:
        raise OfficeVbaContainerError('VBA_OFFICE_INVALID_ZIP') from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise OfficeVbaContainerError(
                'VBA_OFFICE_TOO_MANY_ARCHIVE_ENTRIES',
                413,
                {'max_entries': MAX_ARCHIVE_ENTRIES},
            )

        total_uncompressed = 0
        highest_ratio = 0.0
        project_info = None
        for info in infos:
            _validate_member_name(info.filename)
            if info.flag_bits & 0x1:
                raise OfficeVbaContainerError(
                    'VBA_OFFICE_ENCRYPTED_ARCHIVE_MEMBER',
                    422,
                    {'member': _safe_module_name(info.filename)},
                )

            total_uncompressed += info.file_size
            if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise OfficeVbaContainerError(
                    'VBA_OFFICE_ARCHIVE_TOO_LARGE_AFTER_DECOMPRESSION',
                    413,
                    {'max_uncompressed_bytes': MAX_ARCHIVE_UNCOMPRESSED_BYTES},
                )

            ratio = info.file_size / max(info.compress_size, 1)
            highest_ratio = max(highest_ratio, ratio)
            if info.file_size > 1_048_576 and ratio > MAX_COMPRESSION_RATIO:
                raise OfficeVbaContainerError(
                    'VBA_OFFICE_SUSPICIOUS_COMPRESSION_RATIO',
                    422,
                    {'max_ratio': MAX_COMPRESSION_RATIO},
                )

            if info.filename.lower() == expected_path.lower():
                project_info = info

        if project_info is None:
            raise OfficeVbaContainerError(
                'VBA_PROJECT_NOT_FOUND',
                422,
                {'expected_path': expected_path},
            )
        if project_info.file_size > MAX_PROJECT_BYTES:
            raise OfficeVbaContainerError(
                'VBA_PROJECT_TOO_LARGE',
                413,
                {'max_project_bytes': MAX_PROJECT_BYTES},
            )

        try:
            project = archive.read(project_info)
        except (BadZipFile, RuntimeError) as exc:
            raise OfficeVbaContainerError('VBA_PROJECT_READ_FAILED') from exc

    if not project:
        raise OfficeVbaContainerError('VBA_PROJECT_EMPTY')

    return project, expected_path, {
        'entries': len(infos),
        'uncompressed_bytes': total_uncompressed,
        'highest_compression_ratio': round(highest_ratio, 2),
        'vba_project_bytes': len(project),
    }


def _decode_macro_source(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue
    raise OfficeVbaContainerError('VBA_MODULE_SOURCE_ENCODING_UNSUPPORTED')


def _extract_modules(project: bytes, *, project_path: str) -> list[dict[str, str]]:
    parser = _parser_factory(project_path, project)
    try:
        if not parser.detect_vba_macros():
            raise OfficeVbaContainerError('VBA_MACROS_NOT_FOUND')

        modules: list[dict[str, str]] = []
        total_chars = 0
        for _container_name, stream_path, vba_filename, vba_code in parser.extract_macros():
            if len(modules) >= MAX_MODULES:
                raise OfficeVbaContainerError(
                    'VBA_TOO_MANY_MODULES',
                    413,
                    {'max_modules': MAX_MODULES},
                )
            source = _decode_macro_source(vba_code)
            total_chars += len(source)
            if total_chars > MAX_TOTAL_VBA_SOURCE_CHARS:
                raise OfficeVbaContainerError(
                    'VBA_SOURCE_EXPANSION_TOO_LARGE',
                    413,
                    {'max_source_chars': MAX_TOTAL_VBA_SOURCE_CHARS},
                )
            modules.append(
                {
                    'name': _safe_module_name(vba_filename),
                    'stream_path': str(stream_path or ''),
                    'source': source,
                }
            )
        if not modules:
            raise OfficeVbaContainerError('VBA_MACROS_NOT_FOUND')
        return modules
    except OfficeVbaContainerError:
        raise
    except Exception as exc:
        raise OfficeVbaContainerError(
            'VBA_PROJECT_PARSE_FAILED',
            422,
            {'parser_error_type': type(exc).__name__},
        ) from None
    finally:
        try:
            parser.close()
        except Exception:
            pass


def _detect_vba_stomping(project: bytes, *, project_path: str) -> dict[str, object]:
    parser = _parser_factory(project_path, project)
    try:
        detector = getattr(parser, 'detect_vba_stomping', None)
        if detector is None:
            return {
                'status': 'indeterminate',
                'detected': None,
                'method': 'oletools.detect_vba_stomping',
                'pcode_engine': 'pcodedmp',
                'reason': 'parser_method_unavailable',
            }
        detected = bool(detector())
        return {
            'status': 'detected' if detected else 'not_detected',
            'detected': detected,
            'method': 'oletools.detect_vba_stomping',
            'pcode_engine': 'pcodedmp',
            'reason': None,
        }
    except Exception as exc:
        return {
            'status': 'indeterminate',
            'detected': None,
            'method': 'oletools.detect_vba_stomping',
            'pcode_engine': 'pcodedmp',
            'reason': 'parser_error',
            'parser_error_type': type(exc).__name__,
        }
    finally:
        try:
            parser.close()
        except Exception:
            pass


def _sum_summary(analyses: list[dict[str, object]], key: str) -> int:
    total = 0
    for analysis in analyses:
        summary = analysis.get('summary') or {}
        total += int(summary.get(key) or 0)
    return total


def _semantic_or_legacy(analysis: dict[str, object]) -> dict[str, object]:
    semantic = analysis.get('semantic_analysis')
    if isinstance(semantic, dict):
        return semantic
    return {
        'status': 'NOT_AVAILABLE_FROM_LEGACY_ANALYZER',
        'execution_performed': False,
        'source_persisted': False,
        'data_flow': {
            'schema_version': '1.0.0',
            'nodes': [],
            'edges': [],
            'sinks': [],
            'summary': {'nodes': 0, 'edges': 0, 'sinks': 0, 'procedures_with_flow': 0},
        },
        'test_candidates': [],
    }


def analyze_office_vba_container(content: bytes, *, file_name: str) -> dict[str, object]:
    extension = _extension(file_name)
    if extension not in OFFICE_CONTAINER_EXTENSIONS:
        raise OfficeVbaContainerError(
            'VBA_OFFICE_EXTENSION_UNSUPPORTED',
            422,
            {'supported_extensions': sorted(OFFICE_CONTAINER_EXTENSIONS)},
        )

    project, project_path, archive_stats = _validate_archive_and_read_project(
        content,
        extension=extension,
    )
    modules = _extract_modules(project, project_path=project_path)
    stomping = _detect_vba_stomping(project, project_path=project_path)

    analyzed_modules: list[dict[str, object]] = []
    risks: list[dict[str, object]] = []
    requirement_candidates: list[dict[str, object]] = []
    test_candidates: list[dict[str, object]] = []
    analyses: list[dict[str, object]] = []

    for module in modules:
        analysis = analyze_vba_source(module['source'], file_name=module['name'])
        analyses.append(analysis)
        semantic = _semantic_or_legacy(analysis)
        analyzed_modules.append(
            {
                'name': module['name'],
                'stream_path': module['stream_path'],
                'sha256': analysis['sha256'],
                'summary': analysis['summary'],
                'module': analysis['module'],
                'procedures': analysis['procedures'],
                'dependencies': analysis['dependencies'],
                'business_rules': analysis['business_rules'],
                'semantic_analysis': semantic,
            }
        )
        for risk in analysis['risks']:
            risks.append({'module': module['name'], **risk})
        for candidate in analysis['requirement_candidates']:
            requirement_candidates.append({'module': module['name'], **candidate})
        for candidate in semantic['test_candidates']:
            test_candidates.append({'module': module['name'], **candidate})

    if stomping['status'] == 'detected':
        risks.append(
            {
                'module': None,
                'code': 'VBA_STOMPING_DETECTED',
                'severity': 'high',
                'message': 'Há divergência entre o código-fonte VBA e o P-code compilado.',
                'evidence': 'oletools.detect_vba_stomping',
                'requires_human_review': True,
            }
        )
    elif stomping['status'] == 'indeterminate':
        risks.append(
            {
                'module': None,
                'code': 'VBA_STOMPING_ASSESSMENT_INDETERMINATE',
                'severity': 'medium',
                'message': 'A comparação entre fonte VBA e P-code não pôde ser concluída.',
                'evidence': str(stomping.get('reason') or 'unknown'),
                'requires_human_review': True,
            }
        )

    risks_by_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for risk in risks:
        severity = str(risk.get('severity') or '').lower()
        if severity in risks_by_severity:
            risks_by_severity[severity] += 1

    integrity_status = 'NO_INDICATION'
    if stomping['status'] == 'detected':
        integrity_status = 'REVIEW_REQUIRED'
    elif stomping['status'] == 'indeterminate':
        integrity_status = 'INDETERMINATE'

    return {
        'schema_version': '1.2.0',
        'analyzer': 'reqsys-vba-office-container-static',
        'analysis_type': 'static_only',
        'execution_performed': False,
        'automatic_incorporation': False,
        'source_persisted': False,
        'status': 'AGUARDANDO_REVISAO_HUMANA',
        'container': {
            'file_name': file_name,
            'extension': extension,
            'sha256': hashlib.sha256(content).hexdigest(),
            'vba_project_path': project_path,
            'vba_project_sha256': hashlib.sha256(project).hexdigest(),
            'archive': archive_stats,
        },
        'integrity': {
            'status': integrity_status,
            'vba_stomping': stomping,
            'source_vs_pcode_checked': stomping['status'] != 'indeterminate',
            'execution_performed': False,
        },
        'summary': {
            'modules': len(analyzed_modules),
            'procedures': _sum_summary(analyses, 'procedures'),
            'dependencies': _sum_summary(analyses, 'dependencies'),
            'business_rules': _sum_summary(analyses, 'business_rules'),
            'data_flow_nodes': _sum_summary(analyses, 'data_flow_nodes'),
            'data_flow_edges': _sum_summary(analyses, 'data_flow_edges'),
            'data_flow_sinks': _sum_summary(analyses, 'data_flow_sinks'),
            'test_candidates': len(test_candidates),
            'risks': len(risks),
            'risks_by_severity': risks_by_severity,
            'requirement_candidates': len(requirement_candidates),
            'vba_stomping_status': stomping['status'],
        },
        'modules': analyzed_modules,
        'risks': risks,
        'requirement_candidates': requirement_candidates,
        'test_candidates': test_candidates,
        'modernization_plan': [
            {
                'priority': 'P0',
                'action': 'Revisar divergência fonte/P-code antes de confiar no código-fonte VBA.',
                'required': stomping['status'] != 'not_detected',
            },
            {
                'priority': 'P0',
                'action': 'Revisar riscos críticos e segredos antes de qualquer modernização.',
                'required': risks_by_severity['critical'] > 0,
            },
            {
                'priority': 'P1',
                'action': 'Validar regras, fluxo de dados e candidatos a requisito/teste com responsável de negócio.',
                'required': bool(requirement_candidates or test_candidates),
            },
            {
                'priority': 'P2',
                'action': 'Substituir automações Office/COM por serviços e APIs governados onde aplicável.',
                'required': True,
            },
        ],
    }
