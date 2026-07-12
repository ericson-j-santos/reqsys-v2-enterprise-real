#!/usr/bin/env python3
"""Valida a maturidade mínima da estratégia de testes do ReqSys.

O gate separa capacidades obrigatórias de capacidades avançadas monitoradas.
Gera evidência JSON determinística para auditoria e evolução incremental.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "test-quality-gate.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "test-quality-gate" / "report.json"


def carregar_politica(caminho: Path) -> dict[str, Any]:
    with caminho.open(encoding="utf-8") as arquivo:
        politica = json.load(arquivo)

    obrigatorios = politica.get("required_capabilities", [])
    evidencias = politica.get("evidence_patterns", {})
    ausentes = [item for item in obrigatorios if item not in evidencias]
    if ausentes:
        raise ValueError(f"Capacidades obrigatórias sem padrões: {', '.join(ausentes)}")
    return politica


def localizar_evidencias(raiz: Path, padroes: list[str]) -> list[str]:
    encontrados: set[str] = set()
    for padrao in padroes:
        for caminho in raiz.glob(padrao):
            if caminho.is_file():
                encontrados.add(caminho.relative_to(raiz).as_posix())
    return sorted(encontrados)


def avaliar(raiz: Path, politica: dict[str, Any]) -> dict[str, Any]:
    obrigatorios = set(politica["required_capabilities"])
    consultivos = set(politica.get("advisory_capabilities", []))
    capacidades: dict[str, Any] = {}

    for nome, padroes in politica["evidence_patterns"].items():
        evidencias = localizar_evidencias(raiz, padroes)
        capacidades[nome] = {
            "status": "presente" if evidencias else "ausente",
            "required": nome in obrigatorios,
            "advisory": nome in consultivos,
            "evidence_count": len(evidencias),
            "evidence": evidencias[:50],
        }

    faltantes = sorted(
        nome for nome in obrigatorios if capacidades.get(nome, {}).get("status") != "presente"
    )
    avancadas_pendentes = sorted(
        nome for nome in consultivos if capacidades.get(nome, {}).get("status") != "presente"
    )

    return {
        "schema_version": politica["schema_version"],
        "gate": "golden-test-quality",
        "status": "pass" if not faltantes else "fail",
        "minimum_backend_coverage_percent": politica["minimum_backend_coverage_percent"],
        "required_missing": faltantes,
        "advisory_missing": avancadas_pendentes,
        "capabilities": capacidades,
    }


def salvar_relatorio(relatorio: dict[str, Any], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    argumentos = parser.parse_args()

    try:
        politica = carregar_politica(argumentos.policy)
        relatorio = avaliar(ROOT, politica)
        salvar_relatorio(relatorio, argumentos.output)
    except (OSError, ValueError, json.JSONDecodeError) as erro:
        print(f"Erro ao validar política de testes: {erro}", file=sys.stderr)
        return 2

    if argumentos.json:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Test Quality Gate: {relatorio['status'].upper()}")
        print(f"Obrigatórios ausentes: {', '.join(relatorio['required_missing']) or 'nenhum'}")
        print(f"Avançados pendentes: {', '.join(relatorio['advisory_missing']) or 'nenhum'}")

    return 0 if relatorio["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
