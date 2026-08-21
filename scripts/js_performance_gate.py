#!/usr/bin/env python3
"""
Gate arquitetural de performance para JavaScript/TypeScript/Vue.

Objetivo:
- bloquear novos padrões síncronos de alto risco em código de runtime;
- sinalizar heurísticas que merecem revisão sem gerar falso positivo impeditivo;
- operar incrementalmente por diff em PRs;
- permitir exceções explícitas, locais e justificadas.

Uso:
    python scripts/js_performance_gate.py --base-ref origin/main
    python scripts/js_performance_gate.py --all
    python scripts/js_performance_gate.py --paths frontend/src/main.js

Supressão local:
    // performance-gate: allow PERF001 reason=leitura única no bootstrap antes do servidor iniciar
A supressão vale para a própria linha ou para a linha imediatamente seguinte.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

VERSION = "1.0.0"

SUPPORTED_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue"}

DEFAULT_RUNTIME_PREFIXES = (
    "frontend/src/",
    "src/",
    "app/",
    "server/",
    "services/",
    "packages/",
)

DEFAULT_EXCLUDED_PARTS = (
    "/node_modules/",
    "/dist/",
    "/build/",
    "/coverage/",
    "/vendor/",
    "/.venv/",
    "/venv/",
    "/tests/",
    "/test/",
    "/__tests__/",
    "/fixtures/",
    "/examples/",
)

SYNC_FS_APIS = (
    "readFileSync",
    "writeFileSync",
    "appendFileSync",
    "statSync",
    "lstatSync",
    "readdirSync",
    "mkdirSync",
    "rmSync",
    "rmdirSync",
    "unlinkSync",
    "copyFileSync",
    "renameSync",
    "openSync",
    "closeSync",
    "accessSync",
    "realpathSync",
)

SYNC_PROCESS_APIS = ("execSync", "spawnSync", "execFileSync")
SYNC_CRYPTO_APIS = ("pbkdf2Sync", "scryptSync", "generateKeyPairSync", "generateKeySync")

SUPPRESSION_RE = re.compile(
    r"performance-gate:\s*allow\s+(PERF\d{3})\s+reason=(.+)$",
    re.IGNORECASE,
)

ENDPOINT_RE = re.compile(
    r"\b(?:app|router|server)\s*\.\s*(?:get|post|put|patch|delete|options|head|use)\s*\(",
    re.IGNORECASE,
)

CHAINED_ARRAY_RE = re.compile(
    r"\.(?:map|filter|flatMap)\s*\([^;]{0,600}?\)\s*\.(?:map|filter|flatMap|reduce)\s*\(",
    re.DOTALL,
)

CONSOLE_RE = re.compile(r"\bconsole\.(?:log|debug|info)\s*\(")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    evidence: str
    suppressed: bool = False
    suppression_reason: str | None = None


def _line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _line_text(text: str, line_no: int) -> str:
    lines = text.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()[:240]
    return ""


def _suppression_for(lines: Sequence[str], line_no: int, rule_id: str) -> str | None:
    for candidate in (line_no, line_no - 1):
        if candidate < 1 or candidate > len(lines):
            continue
        match = SUPPRESSION_RE.search(lines[candidate - 1])
        if match and match.group(1).upper() == rule_id.upper():
            reason = match.group(2).strip()
            if len(reason) >= 12:
                return reason
    return None


def _is_excluded(path: Path) -> bool:
    normalized = "/" + path.as_posix().lstrip("/")
    if any(part in normalized for part in DEFAULT_EXCLUDED_PARTS):
        return True

    name = path.name.lower()
    if (
        name.endswith(".test.js")
        or name.endswith(".test.ts")
        or name.endswith(".spec.js")
        or name.endswith(".spec.ts")
        or name.startswith("vite.config.")
        or name.startswith("playwright.config.")
    ):
        return True
    return False


def _is_runtime_path(path: Path) -> bool:
    normalized = path.as_posix().lstrip("./")
    return any(normalized.startswith(prefix) for prefix in DEFAULT_RUNTIME_PREFIXES)


def _matches_api(text: str, api_names: Sequence[str]) -> Iterable[re.Match[str]]:
    joined = "|".join(re.escape(name) for name in api_names)
    return re.finditer(rf"\b(?:{joined})\s*\(", text)


def analyze_text(path: Path, text: str, console_threshold: int = 8) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    runtime = _is_runtime_path(path)

    def add(rule_id: str, severity: str, pos: int, message: str) -> None:
        line_no = _line_number(text, pos)
        suppression = _suppression_for(lines, line_no, rule_id)
        findings.append(
            Finding(
                rule_id=rule_id,
                severity=severity,
                path=path.as_posix(),
                line=line_no,
                message=message,
                evidence=_line_text(text, line_no),
                suppressed=suppression is not None,
                suppression_reason=suppression,
            )
        )

    for match in _matches_api(text, SYNC_FS_APIS):
        add(
            "PERF001",
            "error" if runtime else "warning",
            match.start(),
            "API síncrona de filesystem pode bloquear o event loop; prefira fs/promises, streams ou processamento fora do caminho crítico.",
        )

    for match in _matches_api(text, SYNC_PROCESS_APIS):
        add(
            "PERF002",
            "error" if runtime else "warning",
            match.start(),
            "API síncrona de child_process bloqueia o event loop; prefira exec/spawn assíncrono com timeout e controle de concorrência.",
        )

    for match in _matches_api(text, SYNC_CRYPTO_APIS):
        add(
            "PERF003",
            "error" if runtime else "warning",
            match.start(),
            "Operação criptográfica síncrona de custo relevante; use variante assíncrona ou worker thread.",
        )

    for match in CHAINED_ARRAY_RE.finditer(text):
        add(
            "PERF004",
            "warning",
            match.start(),
            "Cadeia de transformações cria múltiplas passagens/alocações; para coleções grandes avalie loop único, iterator, stream ou processamento incremental.",
        )

    console_matches = list(CONSOLE_RE.finditer(text))
    if runtime and len(console_matches) > console_threshold:
        add(
            "PERF005",
            "warning",
            console_matches[console_threshold].start(),
            f"Arquivo contém {len(console_matches)} chamadas console.log/debug/info; acima do limite {console_threshold}. Prefira logger estruturado e assíncrono.",
        )

    # Heurística de endpoint: amplia a criticidade quando um handler HTTP contém
    # APIs síncronas em uma janela local de código.
    for endpoint in ENDPOINT_RE.finditer(text):
        window_end = min(len(text), endpoint.start() + 2200)
        window = text[endpoint.start():window_end]
        sync_names = SYNC_FS_APIS + SYNC_PROCESS_APIS + SYNC_CRYPTO_APIS
        sync_match = next(_matches_api(window, sync_names), None)
        if sync_match:
            absolute = endpoint.start() + sync_match.start()
            add(
                "PERF006",
                "error",
                absolute,
                "Operação síncrona detectada dentro/próxima de handler HTTP; mova I/O/CPU para fluxo assíncrono, fila ou worker.",
            )

        loop_match = re.search(r"\b(?:for|while)\s*\([^)]*\)\s*\{", window)
        if loop_match and re.search(r"\.(?:map|filter|reduce|sort)\s*\(", window):
            add(
                "PERF007",
                "warning",
                endpoint.start() + loop_match.start(),
                "Handler HTTP combina loop e transformação de coleção; valide complexidade, volume máximo e event-loop lag.",
            )

    return findings


def _git_changed_files(base_ref: str) -> list[Path]:
    command = ["git", "diff", "--name-only", "--diff-filter=ACMRT", f"{base_ref}...HEAD"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Falha ao obter diff contra {base_ref}: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return [Path(line.strip()) for line in completed.stdout.splitlines() if line.strip()]


def _all_supported_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            try:
                relative = path.relative_to(root)
            except ValueError:
                relative = path
            if not _is_excluded(relative):
                result.append(relative)
    return sorted(result)


def _eligible_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        normalized = Path(path.as_posix().lstrip("./"))
        key = normalized.as_posix()
        if key in seen:
            continue
        seen.add(key)
        if normalized.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if _is_excluded(normalized):
            continue
        if not normalized.exists():
            continue
        result.append(normalized)
    return sorted(result)


def run(paths: Sequence[Path], console_threshold: int) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    scanned = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(analyze_text(path, text, console_threshold=console_threshold))
        scanned += 1
    return findings, scanned


def _summary(findings: Sequence[Finding], scanned: int) -> dict[str, object]:
    active = [item for item in findings if not item.suppressed]
    blockers = [item for item in active if item.severity == "error"]
    warnings = [item for item in active if item.severity == "warning"]
    suppressed = [item for item in findings if item.suppressed]
    return {
        "version": VERSION,
        "scanned_files": scanned,
        "findings": len(active),
        "blockers": len(blockers),
        "warnings": len(warnings),
        "suppressed": len(suppressed),
        "status": "blocked" if blockers else "passed",
    }


def _print_human(findings: Sequence[Finding], summary: dict[str, object]) -> None:
    print(
        f"JS Performance Gate v{VERSION}: status={summary['status']} "
        f"scanned={summary['scanned_files']} blockers={summary['blockers']} "
        f"warnings={summary['warnings']} suppressed={summary['suppressed']}"
    )
    for item in findings:
        marker = "SUPPRESSED" if item.suppressed else item.severity.upper()
        print(f"{marker} {item.rule_id} {item.path}:{item.line} - {item.message}")
        if item.evidence:
            print(f"  > {item.evidence}")
        if item.suppressed:
            print(f"  reason: {item.suppression_reason}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base-ref", help="Ref base para analisar somente arquivos alterados.")
    source.add_argument("--all", action="store_true", help="Analisa todos os arquivos suportados.")
    source.add_argument("--paths", nargs="+", help="Lista explícita de arquivos.")
    parser.add_argument("--console-threshold", type=int, default=8)
    parser.add_argument("--report", type=Path, help="Grava evidência JSON.")
    parser.add_argument("--json", action="store_true", help="Emite resultado JSON no stdout.")
    args = parser.parse_args(argv)

    if args.console_threshold < 0:
        parser.error("--console-threshold deve ser >= 0")

    try:
        if args.base_ref:
            candidates = _git_changed_files(args.base_ref)
        elif args.all:
            candidates = _all_supported_files(Path("."))
        else:
            candidates = [Path(item) for item in args.paths]
        paths = _eligible_paths(candidates)
        findings, scanned = run(paths, console_threshold=args.console_threshold)
    except RuntimeError as exc:
        print(f"ERROR PERF000 {exc}", file=sys.stderr)
        return 2

    summary = _summary(findings, scanned)
    payload = {
        "summary": summary,
        "findings": [asdict(item) for item in findings],
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        _print_human(findings, summary)

    return 1 if summary["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
