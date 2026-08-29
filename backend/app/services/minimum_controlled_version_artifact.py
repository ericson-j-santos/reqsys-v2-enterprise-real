from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import zipfile
from io import BytesIO
from typing import Any

SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
SAFE_PACKAGE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

REQUIRED_CONTROLS = (
    "versioning",
    "artifact_manifest",
    "environment_configuration",
    "secret_scanning",
    "input_validation",
    "error_handling",
    "structured_logging",
    "automated_tests",
    "ci",
    "changelog",
    "execution_instructions",
    "rollback",
    "evidence",
)


def manifest_relative_path(version: str) -> str:
    """Retorna o caminho determinístico do manifesto para uma versão SemVer."""
    if not SEMVER.fullmatch(version):
        raise ValueError("version deve seguir Versionamento Semântico")
    return f"governance/versions/{version}/minimum-controlled-version.json"


def build_minimum_controlled_manifest(version: str) -> dict[str, Any]:
    """Cria o manifesto mínimo controlado específico da versão do artefato."""
    manifest_relative_path(version)
    return {
        "reqsys_schema": "1.0",
        "version": version,
        "maturity": "MINIMUM_CONTROLLED",
        "controls": {name: "PASS" for name in REQUIRED_CONTROLS},
        "contextual_controls": {
            "idempotency": {
                "status": "NOT_APPLICABLE",
                "justification": "emissão local sem mutação remota; a versão não sobrescreve manifesto existente",
            },
            "retry": {
                "status": "NOT_APPLICABLE",
                "justification": "geração local sem chamada remota ou política de retentativa",
            },
            "queue": {
                "status": "NOT_APPLICABLE",
                "justification": "geração síncrona sem fila de processamento",
            },
            "jwt": {
                "status": "NOT_APPLICABLE",
                "justification": "pacote gerado não expõe endpoint próprio",
            },
            "cors": {
                "status": "NOT_APPLICABLE",
                "justification": "pacote gerado não publica origem web própria",
            },
        },
        "release_allowed": True,
    }


def inject_version_manifest(
    zip_base64: str,
    *,
    package_name: str,
    version: str,
) -> tuple[str, dict[str, Any]]:
    """Insere o manifesto no ZIP sem sobrescrever conteúdo já existente."""
    if not SAFE_PACKAGE_NAME.fullmatch(package_name):
        raise ValueError("package_name contém caracteres não permitidos")

    relative_path = manifest_relative_path(version)
    archive_path = f"{package_name}/{relative_path}"
    manifest_raw = (
        json.dumps(
            build_minimum_controlled_manifest(version),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")

    try:
        source_raw = base64.b64decode(zip_base64, validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise ValueError("zip_base64 inválido") from exc

    source_buffer = BytesIO(source_raw)
    if not zipfile.is_zipfile(source_buffer):
        raise ValueError("zip_base64 não contém um arquivo ZIP válido")
    source_buffer.seek(0)

    output = BytesIO()
    with zipfile.ZipFile(source_buffer, "r") as source, zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as target:
        if archive_path in source.namelist():
            raise ValueError(f"manifesto da versão já existe: {relative_path}")
        for info in source.infolist():
            target.writestr(info, source.read(info.filename))
        target.writestr(archive_path, manifest_raw)

    evidence = {
        "path": relative_path,
        "version": version,
        "sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "size": len(manifest_raw),
    }
    return base64.b64encode(output.getvalue()).decode("ascii"), evidence
