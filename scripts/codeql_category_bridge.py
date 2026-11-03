"""Publica identificadores CodeQL históricos e atuais a partir do mesmo SARIF real.

Não executa análises, não cria achados e não remove configurações anteriores.
A ponte é temporária até uma migração de categorias auditada e autorizada.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

LANGUAGES = frozenset({"javascript-typescript", "python"})


class CategoryBridgeError(ValueError):
    """A evidência CodeQL não permite uma publicação completa e íntegra."""


def stage_codeql_categories(
    input_root: Path,
    output_dir: Path,
    languages: list[str],
    receipt_path: Path,
) -> dict:
    """Cria 4 categorias auditáveis de 2 análises genuínas, sem tocar nos achados."""
    if len(languages) != 2 or set(languages) != LANGUAGES:
        raise CategoryBridgeError("CodeQL exige ambas as linguagens do baseline main")
    if not input_root.is_dir():
        raise CategoryBridgeError("Diretório de evidências SARIF ausente")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CategoryBridgeError("Diretório de publicação não está vazio")
    if receipt_path.parent == output_dir:
        raise CategoryBridgeError("Recibo deve ficar fora do diretório de upload SARIF")

    found: dict[str, tuple[Path, dict, str]] = {}
    for source in sorted(input_root.rglob("processed/upload.sarif")):
        raw = source.read_bytes()
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise CategoryBridgeError(f"SARIF inválido: {source}") from exc
        if not isinstance(payload, dict) or payload.get("version") != "2.1.0":
            raise CategoryBridgeError(f"Versão SARIF inesperada: {source}")
        runs = payload.get("runs")
        if not isinstance(runs, list) or not runs:
            raise CategoryBridgeError(f"Análise CodeQL ausente: {source}")
        categories: set[str] = set()
        for run in runs:
            if not isinstance(run, dict):
                raise CategoryBridgeError(f"Run SARIF inválido: {source}")
            category = run.get("automationDetails", {}).get("id")
            if not isinstance(category, str):
                raise CategoryBridgeError(f"Categoria CodeQL ausente: {source}")
            driver = run.get("tool", {}).get("driver", {})
            if not isinstance(driver, dict) or driver.get("name") != "CodeQL":
                raise CategoryBridgeError(f"Ferramenta SARIF não é CodeQL: {source}")
            if not isinstance(run.get("results", []), list):
                raise CategoryBridgeError(f"Achados SARIF inválidos: {source}")
            categories.add(category)
        if len(categories) != 1:
            raise CategoryBridgeError(f"Categorias mistas ou ausentes: {source}")
        category = categories.pop()
        language = next(
            (item for item in LANGUAGES if category == f"/language:{item}/"), None
        )
        if language is None or language in found:
            raise CategoryBridgeError(f"Categoria inesperada ou duplicada: {category}")
        found[language] = (source, payload, hashlib.sha256(raw).hexdigest())

    if set(found) != LANGUAGES:
        raise CategoryBridgeError(f"Análises ausentes: {sorted(LANGUAGES - set(found))}")

    output_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for language in sorted(LANGUAGES):
        source, original, source_hash = found[language]
        current_id = f"/language:{language}/"
        # SARIF requires "/" to distinguish category from run_id.
        legacy_id = f"language:{language}/"
        primary = output_dir / f"{language}.sarif"
        shutil.copyfile(source, primary)
        if hashlib.sha256(primary.read_bytes()).hexdigest() != source_hash:
            raise CategoryBridgeError(f"Arquivo original alterado: {language}")

        alias = copy.deepcopy(original)
        total_results = 0
        for source_run, alias_run in zip(original["runs"], alias["runs"]):
            alias_run["automationDetails"]["id"] = legacy_id
            total_results += len(source_run.get("results", []))
            restored = copy.deepcopy(alias_run)
            restored["automationDetails"]["id"] = current_id
            if restored != source_run:
                raise CategoryBridgeError(f"Conteúdo da análise foi alterado: {language}")
        legacy = output_dir / f"legacy-{language}.sarif"
        legacy.write_text(
            json.dumps(alias, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        saved = json.loads(legacy.read_text(encoding="utf-8"))
        if saved != alias:
            raise CategoryBridgeError(f"Falha na releitura da categoria histórica: {language}")
        receipts.append(
            {
                "language": language,
                "original_category": current_id,
                "legacy_category": legacy_id,
                "original_sha256": source_hash,
                "legacy_sha256": hashlib.sha256(legacy.read_bytes()).hexdigest(),
                "results_from_codeql": total_results,
                "finding_mutations": 0,
            }
        )

    result = {
        "schema_version": "1.0",
        "status": "staged_for_upload",
        "category_count": len(receipts) * 2,
        "source_analysis_count": len(receipts),
        "categories": receipts,
        "legacy_compatibility_only": True,
        "deletion_performed": False,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--languages-json", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        languages = json.loads(args.languages_json)
        if not isinstance(languages, list):
            raise CategoryBridgeError("Lista de linguagens inválida")
        result = stage_codeql_categories(
            args.input_root, args.output_dir, languages, args.receipt
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
