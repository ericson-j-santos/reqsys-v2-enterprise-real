from __future__ import annotations

import base64
import hashlib
import json
import re
import zipfile
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from app.services.minimum_controlled_version_artifact import (
    REQUIRED_CONTROLS,
    SEMVER,
    manifest_relative_path,
)
from app.services.vba_call_graph import analyze_vba_with_call_graph

POLICY_VERSION = '1.0.0'
TRANSFORM_EXTENSIONS = ('.bas',)
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_SAFE_SOURCE_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*\.bas$', re.IGNORECASE)
_OPTION_EXPLICIT = re.compile(r'^\s*Option\s+Explicit\b', re.IGNORECASE)
_PREAMBLE_LINE = re.compile(r'^\s*(?:Attribute\b|Option\b|\'|$)', re.IGNORECASE)
_SECRET_PATTERNS = (
    (
        'credential_literal',
        re.compile(
            r'(?i)\b(?:password|pwd|secret|client_?secret|api_?key|token|'
            r'access_?token|refresh_?token)\b(?:[$%&!#@])?\s*'
            r'(?:As\s+[^=\r\n]{1,80}\s*)?=\s*"[^"\r\n]{4,}"'
        ),
    ),
    (
        'connection_string_password',
        re.compile(r'(?i)\b(?:password|pwd)\s*=\s*[^;"\r\n]{4,}'),
    ),
    (
        'bearer_literal',
        re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}'),
    ),
    (
        'private_key_material',
        re.compile(r'-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----', re.IGNORECASE),
    ),
    (
        'url_embedded_credential',
        re.compile(r'(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s/]+@'),
    ),
)
_VOLATILE_ANALYSIS_KEYS = {
    'end_line',
    'evidence',
    'first_line',
    'line',
    'lines',
    'option_explicit',
    'sha256',
    'source_line',
    'start_line',
}


class VbaGovernedEvaluationError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        status_code: int = 422,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.context = context or {}


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    ).encode('utf-8')


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _normalize_source(source: str) -> str:
    normalized = source.replace('\r\n', '\n').replace('\r', '\n')
    if not normalized.strip():
        raise VbaGovernedEvaluationError('VBA_GOVERNED_SOURCE_EMPTY')
    return normalized.rstrip('\n') + '\n'


def _validate_source_name(file_name: str) -> str:
    if not _SAFE_SOURCE_NAME.fullmatch(file_name):
        raise VbaGovernedEvaluationError(
            'VBA_GOVERNED_SOURCE_NAME_UNSAFE',
            context={'required_pattern': _SAFE_SOURCE_NAME.pattern},
        )
    return file_name


def _scan_secret_literals(source: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(source.splitlines(), 1):
        for kind, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({'kind': kind, 'line': line_number})
    return findings


def _ensure_option_explicit(source: str) -> tuple[str, dict[str, Any]]:
    normalized = _normalize_source(source)
    lines = normalized.rstrip('\n').split('\n')
    matches = [index for index, line in enumerate(lines) if _OPTION_EXPLICIT.match(line)]
    if len(matches) > 1:
        raise VbaGovernedEvaluationError(
            'VBA_GOVERNED_OPTION_EXPLICIT_DUPLICATED',
            context={'occurrences': len(matches)},
        )
    if matches:
        return normalized, {
            'control': 'option_explicit',
            'status': 'ALREADY_APPLIED',
            'line': matches[0] + 1,
        }

    insertion_index = 0
    while insertion_index < len(lines) and _PREAMBLE_LINE.match(lines[insertion_index]):
        insertion_index += 1
    lines.insert(insertion_index, 'Option Explicit')
    return '\n'.join(lines).rstrip('\n') + '\n', {
        'control': 'option_explicit',
        'status': 'APPLIED',
        'line': insertion_index + 1,
    }


def _static_projection(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _static_projection(item)
            for key, item in sorted(value.items())
            if key not in _VOLATILE_ANALYSIS_KEYS
        }
    if isinstance(value, list):
        return [_static_projection(item) for item in value]
    return value


def _projection_digest(value: Any) -> str:
    return _sha256(_canonical_json(_static_projection(value)))


def _changed_sections(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    before_projection = _static_projection(before)
    after_projection = _static_projection(after)
    keys = sorted(set(before_projection) | set(after_projection))
    return [key for key in keys if before_projection.get(key) != after_projection.get(key)]


def _control_assessment() -> dict[str, Any]:
    statuses = {
        'versioning': 'PASS',
        'artifact_manifest': 'PASS',
        'environment_configuration': 'FAIL',
        'secret_scanning': 'PASS',
        'input_validation': 'FAIL',
        'error_handling': 'FAIL',
        'structured_logging': 'FAIL',
        'automated_tests': 'FAIL',
        'ci': 'FAIL',
        'changelog': 'PASS',
        'execution_instructions': 'FAIL',
        'rollback': 'PASS',
        'evidence': 'PASS',
    }
    assert set(statuses) == set(REQUIRED_CONTROLS)
    return {
        'scope': 'vba_candidate_and_evidence_package',
        'required_controls': statuses,
        'applied_safely': [
            'source_normalization',
            'option_explicit',
            'secret_literal_gate',
            'static_preservation_gate',
            'semantic_versioning',
            'deterministic_checksums',
            'rollback_copy',
        ],
        'not_injected_automatically': [
            'environment_configuration',
            'procedure_input_validation',
            'procedure_error_handling',
            'runtime_structured_logging',
            'vba_compile_or_runtime_ci',
        ],
        'reason': (
            'Generic rewrites of business procedures could change VBA behavior; '
            'these controls require a future isolated dynamic validation.'
        ),
    }


def _vmc_manifest(version: str, controls: dict[str, str]) -> dict[str, Any]:
    contextual_controls: dict[str, Any] = {
        'idempotency': 'PASS',
        'static_preservation': 'PASS',
        'functional_equivalence': 'FAIL',
        'vba_compile_validation': 'FAIL',
        'retry': {
            'status': 'NOT_APPLICABLE',
            'justification': 'deterministic local packaging without remote calls',
        },
        'queue': {
            'status': 'NOT_APPLICABLE',
            'justification': 'synchronous evaluation without a processing queue',
        },
        'jwt': {
            'status': 'NOT_APPLICABLE',
            'justification': 'the generated VBA candidate does not issue tokens',
        },
        'cors': {
            'status': 'NOT_APPLICABLE',
            'justification': 'the generated VBA candidate is not a web origin',
        },
    }
    release_allowed = all(value == 'PASS' for value in controls.values()) and all(
        value != 'FAIL' for value in contextual_controls.values()
    )
    return {
        'reqsys_schema': '1.0',
        'version': version,
        'maturity': 'EXPERIMENTAL',
        'controls': controls,
        'contextual_controls': contextual_controls,
        'release_allowed': release_allowed,
    }


def _file_evidence(files: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {'path': path, 'sha256': _sha256(content), 'size': len(content)}
        for path, content in sorted(files.items())
    ]


def _checksums(files: dict[str, bytes]) -> bytes:
    return ''.join(
        f'{_sha256(content)}  {path}\n' for path, content in sorted(files.items())
    ).encode('utf-8')


def _deterministic_zip(files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=_FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    result = output.getvalue()
    if len(result) > MAX_PACKAGE_BYTES:
        raise VbaGovernedEvaluationError(
            'VBA_GOVERNED_PACKAGE_TOO_LARGE',
            status_code=413,
            context={'max_bytes': MAX_PACKAGE_BYTES},
        )
    return result


def _verify_package(package: bytes) -> None:
    with zipfile.ZipFile(BytesIO(package), 'r') as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if names != sorted(names) or len(names) != len(set(names)):
            raise RuntimeError('VBA_GOVERNED_PACKAGE_ORDER_OR_DUPLICATE')
        for info in infos:
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or '..' in path.parts
                or '\\' in info.filename
                or info.date_time != _FIXED_ZIP_TIMESTAMP
                or info.compress_type != zipfile.ZIP_STORED
            ):
                raise RuntimeError('VBA_GOVERNED_PACKAGE_UNSAFE_MEMBER')

        declared: dict[str, str] = {}
        for line in archive.read('checksums.sha256').decode('utf-8').splitlines():
            digest, path = line.split('  ', 1)
            declared[path] = digest
        expected = set(names) - {'checksums.sha256'}
        if set(declared) != expected:
            raise RuntimeError('VBA_GOVERNED_PACKAGE_CHECKSUM_SET_MISMATCH')
        for path, digest in declared.items():
            if _sha256(archive.read(path)) != digest:
                raise RuntimeError('VBA_GOVERNED_PACKAGE_HASH_MISMATCH')


def evaluate_vba_governed(
    source: str,
    *,
    file_name: str,
    version: str,
    raw_input: bytes | None = None,
) -> dict[str, Any]:
    if not SEMVER.fullmatch(version):
        raise VbaGovernedEvaluationError('VBA_GOVERNED_VERSION_INVALID')
    source_name = _validate_source_name(file_name)
    normalized_source = _normalize_source(source)
    secret_findings = _scan_secret_literals(normalized_source)
    if secret_findings:
        raise VbaGovernedEvaluationError(
            'VBA_GOVERNED_SECRET_LITERAL_BLOCKED',
            context={'findings': secret_findings, 'package_emitted': False},
        )

    original_analysis = analyze_vba_with_call_graph(
        normalized_source,
        file_name=source_name,
    )
    candidate_source, transformation = _ensure_option_explicit(normalized_source)
    candidate_analysis = analyze_vba_with_call_graph(
        candidate_source,
        file_name=source_name,
    )

    before_projection_sha = _projection_digest(original_analysis)
    after_projection_sha = _projection_digest(candidate_analysis)
    changed_sections = _changed_sections(original_analysis, candidate_analysis)
    option_explicit = bool(candidate_analysis['module']['option_explicit'])
    if before_projection_sha != after_projection_sha or not option_explicit:
        raise VbaGovernedEvaluationError(
            'VBA_GOVERNED_STATIC_BEHAVIOR_DRIFT',
            context={
                'before_projection_sha256': before_projection_sha,
                'after_projection_sha256': after_projection_sha,
                'changed_sections': changed_sections,
                'package_emitted': False,
            },
        )

    original_raw = normalized_source.encode('utf-8')
    candidate_raw = candidate_source.encode('utf-8')
    raw_input_sha = _sha256(raw_input if raw_input is not None else source.encode('utf-8'))
    normalized_source_sha = _sha256(original_raw)
    candidate_sha = _sha256(candidate_raw)
    evaluation_id = _sha256(
        (
            f'{raw_input_sha}:{normalized_source_sha}:{candidate_sha}:'
            f'{version}:{POLICY_VERSION}'
        ).encode('ascii')
    )
    preservation = {
        'status': 'PASS',
        'scope': 'static_projection_only',
        'before_projection_sha256': before_projection_sha,
        'after_projection_sha256': after_projection_sha,
        'changed_sections': [],
        'functional_equivalence': 'NOT_PROVEN',
        'compile_validation': 'NOT_RUN',
        'dynamic_validation_required': True,
        'execution_performed': False,
    }
    controls = _control_assessment()
    vmc = _vmc_manifest(version, controls['required_controls'])
    if vmc['release_allowed']:
        raise RuntimeError('VBA_GOVERNED_FAIL_CLOSED_RELEASE_ASSERTION')

    limitations = {
        'candidate_status': 'PROPOSED_NOT_RELEASED',
        'functional_equivalence': 'NOT_PROVEN',
        'compile_validation': 'NOT_RUN',
        'dynamic_validation': 'FUTURE_REQUIRED',
        'unsupported_proof_boundaries': [
            'Office or VBA runtime behavior',
            'workbook state and event ordering',
            'COM and external system side effects',
            'locale and host-specific behavior',
            'compiled P-code equivalence',
        ],
        'execution_performed': False,
        'office_execution': False,
        'source_persisted': False,
        'source_included_in_returned_package': True,
        'server_persistence_performed': False,
    }
    test_plan = {
        'status': 'PROPOSED_NOT_EXECUTED',
        'static_candidates': original_analysis['semantic_analysis']['test_candidates'],
        'future_dynamic_stages': [
            'compile the candidate in an isolated supported Office environment',
            'run approved fixtures against original and candidate with side effects mocked',
            'compare outputs and approved side effects',
            'record host, Office version, fixture hashes, logs, and rollback result',
        ],
        'execution_performed': False,
    }

    files: dict[str, bytes] = {
        f'source/original-normalized/{source_name}': original_raw,
        f'source/candidate/{source_name}': candidate_raw,
        'analysis/original.json': _canonical_json(original_analysis),
        'analysis/candidate.json': _canonical_json(candidate_analysis),
        'controls/control-assessment.json': _canonical_json(controls),
        'preservation/static-preservation.json': _canonical_json(preservation),
        'evidence/limitations.json': _canonical_json(limitations),
        'evidence/test-plan.json': _canonical_json(test_plan),
        manifest_relative_path(version): _canonical_json(vmc),
        'README.md': (
            '# ReqSys VBA governed evaluation\n\n'
            f'- Version: `{version}`\n'
            '- Status: `AWAITING_DYNAMIC_VALIDATION`\n'
            '- Candidate: `PROPOSED_NOT_RELEASED`\n'
            '- Static preservation: `PASS`\n'
            '- Functional equivalence: `NOT_PROVEN`\n'
            '- VBA/Office execution: `NOT_RUN`\n\n'
            'The original business module is preserved and the candidate only adds '
            '`Option Explicit` when absent. The original member is normalized to '
            'UTF-8/LF and is not a byte-for-byte copy of the upload. Do not release '
            'the candidate until the '
            'future isolated dynamic validation in `evidence/test-plan.json` passes.\n'
        ).encode('utf-8'),
        'CHANGELOG.md': (
            '# Changelog\n\n'
            f'## {version}\n\n'
            '- Normalized the exported module to UTF-8/LF.\n'
            '- Applied or confirmed `Option Explicit`.\n'
            '- Added static preservation and governance evidence.\n'
        ).encode('utf-8'),
        'ROLLBACK.md': (
            '# Rollback\n\n'
            '1. Do not import the candidate module.\n'
            f'2. Restore `source/original-normalized/{source_name}`.\n'
            f'3. Verify normalized SHA-256 `{normalized_source_sha}`.\n'
            '4. Record the reason and keep this evidence package.\n'
        ).encode('utf-8'),
    }
    package_manifest = {
        'schema_version': '1.0',
        'contract': 'reqsys-vba-governed-evaluation-v1',
        'package_type': 'reqsys_vba_governed_evaluation',
        'policy_version': POLICY_VERSION,
        'evaluation_id': evaluation_id,
        'version': version,
        'source_file': source_name,
        'raw_input_sha256': raw_input_sha,
        'normalized_source_sha256': normalized_source_sha,
        'candidate_sha256': candidate_sha,
        'status': 'AWAITING_DYNAMIC_VALIDATION',
        'candidate_status': 'PROPOSED_NOT_RELEASED',
        'static_preservation': 'PASS',
        'functional_equivalence': 'NOT_PROVEN',
        'compile_validation': 'NOT_RUN',
        'dynamic_validation_required': True,
        'release_allowed': False,
        'execution_performed': False,
        'office_execution': False,
        'source_persisted': False,
        'source_included_in_returned_package': True,
        'server_persistence_performed': False,
        'files': _file_evidence(files),
    }
    files['manifest.json'] = _canonical_json(package_manifest)
    files['checksums.sha256'] = _checksums(files)
    package_raw = _deterministic_zip(files)
    _verify_package(package_raw)

    package_sha = _sha256(package_raw)
    package_name = f'{source_name[:-4]}-{version}-vba-governed.zip'
    return {
        'schema_version': '1.0.0',
        'contract': 'reqsys-vba-governed-evaluation-v1',
        'status': 'AWAITING_DYNAMIC_VALIDATION',
        'candidate_status': 'PROPOSED_NOT_RELEASED',
        'analysis_type': 'static_only',
        'automatic_incorporation': False,
        'requires_human_validation': True,
        'dynamic_equivalence_claimed': False,
        'evaluation_id': evaluation_id,
        'version': version,
        'analysis': original_analysis,
        'transformation': {
            **transformation,
            'raw_input_sha256': raw_input_sha,
            'normalized_source_sha256': normalized_source_sha,
            'candidate_sha256': candidate_sha,
        },
        'preservation': preservation,
        'control_assessment': controls,
        'minimum_controlled_version': vmc,
        'functional_equivalence': 'NOT_PROVEN',
        'dynamic_validation': 'FUTURE_REQUIRED',
        'release_allowed': False,
        'execution_performed': False,
        'office_execution': False,
        'source_persisted': False,
        'source_included_in_returned_package': True,
        'server_persistence_performed': False,
        'package': {
            'file_name': package_name,
            'media_type': 'application/zip',
            'sha256': package_sha,
            'size': len(package_raw),
            'base64': base64.b64encode(package_raw).decode('ascii'),
        },
    }
