#!/usr/bin/env python3
"""Orquestrador report-only da camada de testes do ReqSys.

Incremento inicial do ReqSys Quality Fabric:
- lê a matriz versionada em governance/testing/test-matrix.yaml;
- seleciona suítes pelo perfil e, opcionalmente, pelos arquivos alterados;
- executa comandos sem shell, com timeout e diretório confinado ao repositório;
- gera evidence JSON, resumo Markdown, JUnit e SHA-256 do manifesto;
- permanece report-only por padrão. Use --enforce explicitamente para retornar
  código diferente de zero quando uma suíte falhar.

O arquivo .yaml inicial usa sintaxe JSON, que é YAML 1.2 válido. Isso mantém o
orquestrador sem dependência obrigatória de PyYAML. Se o manifesto evoluir para
sintaxe YAML não compatível com JSON, PyYAML será utilizado quando instalado.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "governance" / "testing" / "test-matrix.yaml"
DEFAULT_SCHEMA = ROOT / "governance" / "testing" / "schemas" / "test-matrix.schema.json"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "quality-fabric" / "runtime"
MAX_CAPTURE_CHARS = 8_000

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|AUTHORIZATION)[A-Z0-9_]*)"
    r"\s*[:=]\s*([^\s,;]+)"
)


class ManifestError(ValueError):
    """Manifesto inválido ou inseguro."""


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ManifestError(
                f"{path} não é JSON/YAML compatível com a biblioteca padrão; "
                "instale PyYAML para usar sintaxe YAML expandida."
            ) from exc
        payload = yaml.safe_load(text)

    if not isinstance(payload, dict):
        raise ManifestError(f"{path} deve conter um objeto no nível raiz.")
    return payload


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = _load_yaml_or_json(path)
    validate_manifest(payload)
    return payload


def load_schema(path: Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ManifestError("Schema JSON inválido.")
    return payload


def _safe_relative_path(value: str, *, field: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ManifestError(f"{field} deve ser relativo e permanecer dentro do repositório: {value!r}")
    return path


def validate_manifest(payload: dict[str, Any]) -> None:
    required = {"schema_version", "default_profile", "mode", "profiles", "suites"}
    missing = required - payload.keys()
    if missing:
        raise ManifestError(f"Campos obrigatórios ausentes: {', '.join(sorted(missing))}")

    if payload["mode"] not in {"report-only", "enforced"}:
        raise ManifestError("mode deve ser 'report-only' ou 'enforced'.")

    profiles = payload["profiles"]
    suites = payload["suites"]
    if not isinstance(profiles, dict) or not profiles:
        raise ManifestError("profiles deve ser um objeto não vazio.")
    if not isinstance(suites, dict) or not suites:
        raise ManifestError("suites deve ser um objeto não vazio.")

    default_profile = payload["default_profile"]
    if default_profile not in profiles:
        raise ManifestError(f"default_profile desconhecido: {default_profile!r}")

    for profile_name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ManifestError(f"Perfil {profile_name!r} deve ser um objeto.")
        suite_ids = profile.get("suites")
        if not isinstance(suite_ids, list) or not suite_ids:
            raise ManifestError(f"Perfil {profile_name!r} deve declarar suites.")
        unknown = [suite_id for suite_id in suite_ids if suite_id not in suites]
        if unknown:
            raise ManifestError(
                f"Perfil {profile_name!r} referencia suites inexistentes: {', '.join(unknown)}"
            )

    for suite_id, suite in suites.items():
        if not isinstance(suite, dict):
            raise ManifestError(f"Suite {suite_id!r} deve ser um objeto.")

        _safe_relative_path(str(suite.get("cwd", "")), field=f"suites.{suite_id}.cwd")

        command = suite.get("command")
        if not isinstance(command, list) or not command or not all(
            isinstance(item, str) and item for item in command
        ):
            raise ManifestError(f"Suite {suite_id!r} deve declarar command como lista de strings.")

        timeout_seconds = suite.get("timeout_seconds")
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 7200:
            raise ManifestError(f"Suite {suite_id!r} possui timeout_seconds inválido.")

        if not isinstance(suite.get("always_run"), bool):
            raise ManifestError(f"Suite {suite_id!r} deve declarar always_run booleano.")

        paths = suite.get("paths")
        if not isinstance(paths, list) or not all(isinstance(item, str) and item for item in paths):
            raise ManifestError(f"Suite {suite_id!r} deve declarar paths como lista de strings.")


def resolve_command(command: list[str]) -> list[str]:
    return [sys.executable if item == "{python}" else item for item in command]


def changed_files(base_sha: str, head_sha: str) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", base_sha, head_sha],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = sanitize_output(proc.stderr or proc.stdout)
        raise RuntimeError(f"Não foi possível calcular arquivos alterados: {detail}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def select_suites(
    manifest: dict[str, Any],
    profile_name: str,
    changed: list[str] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    profiles = manifest["profiles"]
    if profile_name not in profiles:
        raise ManifestError(
            f"Perfil {profile_name!r} inexistente. Disponíveis: {', '.join(sorted(profiles))}"
        )

    selected: list[tuple[str, dict[str, Any]]] = []
    for suite_id in profiles[profile_name]["suites"]:
        suite = manifest["suites"][suite_id]
        if changed is None or suite["always_run"] or any(
            _matches_any(path, suite["paths"]) for path in changed
        ):
            selected.append((suite_id, suite))
    return selected


def sanitize_output(value: str | None) -> str:
    if not value:
        return ""
    redacted = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    if len(redacted) > MAX_CAPTURE_CHARS:
        return "[...truncado...]\n" + redacted[-MAX_CAPTURE_CHARS:]
    return redacted


def _safe_workdir(cwd: str) -> Path:
    relative = _safe_relative_path(cwd, field="cwd")
    candidate = (ROOT / relative).resolve()
    root_resolved = ROOT.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ManifestError(f"Diretório de execução escapa do repositório: {cwd!r}")
    if not candidate.is_dir():
        raise ManifestError(f"Diretório de execução não existe: {cwd!r}")
    return candidate


def run_suite(
    suite_id: str,
    suite: dict[str, Any],
    *,
    profile_name: str,
    correlation_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    command = resolve_command(list(suite["command"]))
    workdir = _safe_workdir(str(suite["cwd"]))

    base_result: dict[str, Any] = {
        "id": suite_id,
        "description": suite.get("description", ""),
        "evidence_kind": suite.get("evidence_kind", "governance"),
        "cwd": str(suite["cwd"]),
        "command": command,
        "timeout_seconds": suite["timeout_seconds"],
    }

    if dry_run:
        return {
            **base_result,
            "status": "planned",
            "exit_code": None,
            "duration_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    env = os.environ.copy()
    env["REQSYS_QUALITY_PROFILE"] = profile_name
    env["REQSYS_CORRELATION_ID"] = correlation_id
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=workdir,
            env=env,
            text=True,
            capture_output=True,
            timeout=suite["timeout_seconds"],
            check=False,
        )
        status = "passed" if proc.returncode == 0 else "failed"
        return {
            **base_result,
            "status": status,
            "exit_code": proc.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_tail": sanitize_output(proc.stdout),
            "stderr_tail": sanitize_output(proc.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            **base_result,
            "status": "timeout",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_tail": sanitize_output(
                exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
            ),
            "stderr_tail": sanitize_output(
                exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
            ),
        }
    except OSError as exc:
        return {
            **base_result,
            "status": "error",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_tail": "",
            "stderr_tail": sanitize_output(str(exc)),
        }


def current_commit_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "unknown"


def build_evidence(
    *,
    manifest_path: Path,
    profile_name: str,
    selected: list[tuple[str, dict[str, Any]]],
    changed: list[str] | None,
    dry_run: bool,
) -> dict[str, Any]:
    sha = current_commit_sha()
    correlation_id = f"qf-{sha[:8]}-{uuid.uuid4().hex[:8]}"
    started_at = int(time.time())

    results = [
        run_suite(
            suite_id,
            suite,
            profile_name=profile_name,
            correlation_id=correlation_id,
            dry_run=dry_run,
        )
        for suite_id, suite in selected
    ]

    statuses = [result["status"] for result in results]
    if dry_run:
        decision = "planned"
    elif all(status == "passed" for status in statuses):
        decision = "pass"
    else:
        decision = "fail"

    return {
        "schema_version": "1.0",
        "mode": "report-only",
        "profile": profile_name,
        "commit_sha": sha,
        "correlation_id": correlation_id,
        "started_at_epoch": started_at,
        "finished_at_epoch": int(time.time()),
        "changed_files": changed,
        "selected_suites": [suite_id for suite_id, _ in selected],
        "summary": {
            "total": len(results),
            "passed": statuses.count("passed"),
            "failed": statuses.count("failed"),
            "timeout": statuses.count("timeout"),
            "error": statuses.count("error"),
            "planned": statuses.count("planned"),
        },
        "decision": decision,
        "results": results,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    summary = evidence["summary"]
    lines = [
        "# ReqSys Quality Fabric — Evidence",
        "",
        f"- Perfil: `{evidence['profile']}`",
        f"- Commit: `{evidence['commit_sha']}`",
        f"- Correlation ID: `{evidence['correlation_id']}`",
        f"- Decisão: **{evidence['decision']}**",
        f"- Modo: `{evidence['mode']}`",
        "",
        "| Suite | Tipo | Status | Duração (s) |",
        "|---|---|---|---:|",
    ]
    for result in evidence["results"]:
        lines.append(
            f"| `{result['id']}` | {result['evidence_kind']} | "
            f"{result['status']} | {result['duration_seconds']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Resumo",
            "",
            f"- Total: {summary['total']}",
            f"- Passaram: {summary['passed']}",
            f"- Falharam: {summary['failed']}",
            f"- Timeout: {summary['timeout']}",
            f"- Erro de execução: {summary['error']}",
            f"- Planejados: {summary['planned']}",
            "",
            "> Este incremento é report-only: não altera os gates existentes do repositório.",
            "",
        ]
    )
    return "\n".join(lines)


def build_junit(evidence: dict[str, Any]) -> str:
    results = evidence["results"]
    failures = sum(result["status"] in {"failed", "timeout", "error"} for result in results)
    suite = ET.Element(
        "testsuite",
        {
            "name": f"reqsys-quality-fabric-{evidence['profile']}",
            "tests": str(len(results)),
            "failures": str(failures),
            "errors": "0",
        },
    )
    for result in results:
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "quality_fabric",
                "name": result["id"],
                "time": f"{result['duration_seconds']:.3f}",
            },
        )
        if result["status"] in {"failed", "timeout", "error"}:
            failure = ET.SubElement(case, "failure", {"message": result["status"]})
            failure.text = result["stderr_tail"] or result["stdout_tail"]
        elif result["status"] == "planned":
            ET.SubElement(case, "skipped", {"message": "dry-run"})
    return ET.tostring(suite, encoding="unicode") + "\n"


def write_evidence(
    evidence: dict[str, Any],
    output_dir: Path,
    manifest_path: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "quality-evidence.json"
    markdown_path = output_dir / "quality-summary.md"
    junit_path = output_dir / "junit.xml"
    manifest_hash_path = output_dir / "manifest.sha256"

    json_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(evidence), encoding="utf-8")
    junit_path.write_text(build_junit(evidence), encoding="utf-8")
    manifest_hash_path.write_text(
        f"{evidence['manifest_sha256']}  {manifest_path.as_posix()}\n",
        encoding="utf-8",
    )
    return {
        "json": json_path,
        "markdown": markdown_path,
        "junit": junit_path,
        "manifest_sha256": manifest_hash_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ReqSys Quality Fabric — orquestrador report-only")
    parser.add_argument("--profile", help="Perfil definido no manifesto.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--base-sha")
    parser.add_argument("--head-sha")
    parser.add_argument("--changed-file", action="append", dest="changed_files")
    parser.add_argument("--dry-run", action="store_true", help="Planeja sem executar comandos.")
    parser.add_argument("--enforce", action="store_true", help="Retorna exit code 1 quando decision=fail.")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = load_manifest(args.manifest)
    load_schema(args.schema)

    profile_name = args.profile or manifest["default_profile"]

    if bool(args.base_sha) != bool(args.head_sha):
        raise ManifestError("--base-sha e --head-sha devem ser informados juntos.")

    changed = list(args.changed_files) if args.changed_files else None
    if args.base_sha and args.head_sha:
        git_changed = changed_files(args.base_sha, args.head_sha)
        changed = sorted(set((changed or []) + git_changed))

    selected = select_suites(manifest, profile_name, changed)
    evidence = build_evidence(
        manifest_path=args.manifest,
        profile_name=profile_name,
        selected=selected,
        changed=changed,
        dry_run=args.dry_run,
    )
    write_evidence(evidence, args.output_dir, args.manifest)

    if args.print_json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(evidence))

    if args.enforce and evidence["decision"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ManifestError, RuntimeError, OSError) as exc:
        print(f"quality-fabric: erro: {exc}", file=sys.stderr)
        raise SystemExit(2)
