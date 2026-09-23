"""Adaptador ReqSys para o núcleo compartilhado Report Builder Platform.

O domínio do ReqSys permanece neste repositório. Geração/validação genérica de
RDL e integração Fabric são consumidas do pacote externo fixado por SHA em
requirements-report-builder.txt.
"""

from __future__ import annotations

from typing import Any

from report_builder import report_factory as _core

PLATFORM_COMMIT = "07463712333de28a7823491b53c5620bdd4e48b6"
IDENTITY_NAMESPACE = "reqsys:report-factory"

RDL_NS = _core.RDL_NS
RD_NS = _core.RD_NS
DF_NS = _core.DF_NS
FABRIC_BASE_URL = _core.FABRIC_BASE_URL

ReportSpecError = _core.ReportSpecError
FabricApiError = _core.FabricApiError

def q(tag: str) -> str:
    """Qualifica uma tag no namespace RDL 2016 para consumidores ReqSys."""
    return f"{{{RDL_NS}}}{tag}"


def rd(tag: str) -> str:
    """Qualifica uma tag no namespace Report Designer."""
    return f"{{{RD_NS}}}{tag}"


def df(tag: str) -> str:
    """Qualifica uma tag no namespace DefaultFontFamily."""
    return f"{{{DF_NS}}}{tag}"

load_spec = _core.load_spec
validate_spec = _core.validate_spec
validate_rdl = _core.validate_rdl
build_fabric_definition = _core.build_fabric_definition
build_create_request = _core.build_create_request
publish_to_fabric = _core.publish_to_fabric


def generate_rdl(spec: dict[str, Any]) -> str:
    """Gera RDL preservando as identidades determinísticas históricas do ReqSys."""
    return _core.generate_rdl(spec, identity_namespace=IDENTITY_NAMESPACE)


def main(argv: list[str] | None = None) -> int:
    """Mantém a CLI histórica do ReqSys sobre o pacote compartilhado."""
    return _core.main(argv, identity_namespace=IDENTITY_NAMESPACE)


if __name__ == "__main__":
    raise SystemExit(main())
