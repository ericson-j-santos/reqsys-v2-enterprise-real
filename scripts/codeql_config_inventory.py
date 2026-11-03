"""Audita a paridade real de configurações CodeQL na API GitHub (somente leitura)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Callable
from urllib.parse import quote


class CodeQLInventoryError(RuntimeError):
    """O serviço Code Scanning não comprovou paridade de configuração."""


def inventory(
    repository: str,
    pull_ref: str,
    *,
    runner: Callable = subprocess.run,
    clock: Callable = time.monotonic,
    max_pages: int = 20,
    time_budget_seconds: float = 90,
) -> dict:
    """Compara as chaves completas de configuração, sem alterar alertas."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repositório inválido")
    if not re.fullmatch(r"refs/pull/[1-9][0-9]*/merge", pull_ref):
        raise ValueError("Referência de PR inválida")
    if max_pages < 1 or time_budget_seconds <= 0:
        raise ValueError("Limites inválidos")

    seen_at = clock()
    reports = {}
    for label, ref in (("main", "refs/heads/main"), ("pr", pull_ref)):
        latest = {}
        page_count = 0
        complete = False
        for page in range(1, max_pages + 1):
            elapsed = clock() - seen_at
            if elapsed >= time_budget_seconds:
                raise CodeQLInventoryError(f"Prazo de inventário excedido: {label}")
            endpoint = (
                f"repos/{repository}/code-scanning/analyses?"
                f"ref={quote(ref, safe='')}&tool_name=CodeQL&per_page=100&page={page}"
            )
            try:
                response = runner(
                    ["gh", "api", "--method", "GET", endpoint],
                    text=True, capture_output=True, check=False,
                    timeout=min(25, max(1, time_budget_seconds - elapsed)),
                )
            except subprocess.TimeoutExpired as exc:
                raise CodeQLInventoryError(f"Timeout de leitura Code Scanning: {label}") from exc
            if response.returncode:
                raise CodeQLInventoryError(
                    f"API Code Scanning indisponível: {label}, page={page}, exit={response.returncode}"
                )
            try:
                items = json.loads(response.stdout)
            except (TypeError, ValueError) as exc:
                raise CodeQLInventoryError(f"JSON de análise inválido: {label}") from exc
            if not isinstance(items, list) or len(items) > 100:
                raise CodeQLInventoryError(f"Página de análises fora de contrato: {label}")
            page_count += 1
            for item in items:
                if not isinstance(item, dict):
                    raise CodeQLInventoryError(f"Análise inválida: {label}")
                tool = item.get("tool") or {}
                if tool.get("name") != "CodeQL":
                    continue
                key, category = item.get("analysis_key"), item.get("category")
                if not isinstance(key, str) or not key or not isinstance(category, str):
                    raise CodeQLInventoryError(f"Categoria/análise sem identidade: {label}")
                identity = (key, category)
                if identity not in latest:
                    latest[identity] = {
                        "analysis_key": key,
                        "category": category,
                        "commit_sha": item.get("commit_sha"),
                        "created_at": item.get("created_at"),
                        "analysis_id": item.get("id"),
                        "results_count": item.get("results_count"),
                        "ref": item.get("ref"),
                    }
            if len(items) < 100:
                complete = True
                break
        reports[label] = {
            "ref": ref,
            "pages_checked": page_count,
            "complete": complete,
            "configurations": sorted(latest.values(), key=lambda x: (x["analysis_key"], x["category"])),
        }
    main_keys = {
        (x["analysis_key"], x["category"])
        for x in reports["main"]["configurations"]
    }
    pr_keys = {
        (x["analysis_key"], x["category"])
        for x in reports["pr"]["configurations"]
    }
    missing = sorted(main_keys - pr_keys)
    result = {
        "schema_version": "1.0",
        "status": "matched" if (
            not missing
            and all(x["complete"] and x["configurations"] for x in reports.values())
        ) else "incomplete_or_mismatch",
        "reports": reports,
        "missing_main_configurations_in_pr": [
            {"analysis_key": key, "category": category} for key, category in missing
        ],
        "read_only": True,
        "deletions": 0,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pull-ref", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = inventory(args.repository, args.pull_ref)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        if result["status"] != "matched":
            raise SystemExit("CodeQL configuration mismatch: veja o inventário sanitizado acima")
    except (CodeQLInventoryError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
