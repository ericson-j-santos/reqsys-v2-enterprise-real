#!/usr/bin/env python3
"""Gera log semanal do ReqSys usando somente evidências verificáveis do GitHub."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DIMENSIONS = ("implemented", "validated", "evidenced", "consolidated", "governed")
GOOD_CONCLUSIONS = {"success", "neutral", "skipped"}
CONSOLIDATION_PREFIXES = ("docs/", "audit/", "evidence/", "reports/")
GOVERNANCE_PREFIXES = (".sdd/", "governance/", ".github/workflows/", "config/")


class GitHubApiError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        if not token:
            raise ValueError("GITHUB_TOKEN ausente")
        self.token = token
        self.api_url = api_url.rstrip("/")

    def get(self, path: str) -> Any:
        request = Request(
            f"{self.api_url}{path}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "reqsys-weekly-accomplishment-log",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise GitHubApiError(f"GitHub API HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GitHubApiError(f"GitHub API indisponível/inválida: {exc}") from exc

    def paged(self, path: str, *, key: str | None = None, max_pages: int = 10) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            payload = self.get(f"{path}{separator}per_page=100&page={page}")
            items = payload.get(key, []) if key else payload
            if not isinstance(items, list):
                raise GitHubApiError(f"Resposta paginada inválida em {path}")
            result.extend(item for item in items if isinstance(item, dict))
            if len(items) < 100:
                break
        return result


def _file_matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return path == "CHANGELOG.md" or path.startswith(prefixes)


def classify_item(raw: dict[str, Any]) -> dict[str, Any]:
    checks = [c for c in raw.get("checks", []) if isinstance(c, dict)]
    completed = [c for c in checks if c.get("status") == "completed"]
    successful = [c for c in completed if c.get("conclusion") == "success"]
    failed = [c for c in completed if c.get("conclusion") not in GOOD_CONCLUSIONS]
    check_links = [str(c.get("html_url") or "") for c in checks if c.get("html_url")]
    files = [str(path) for path in raw.get("files", []) if str(path).strip()]

    validated = bool(successful) and not failed
    evidenced = bool(raw.get("html_url")) and bool(raw.get("head_sha")) and bool(check_links)
    consolidated = any(_file_matches(path, CONSOLIDATION_PREFIXES) for path in files)
    governed = validated and any(path.startswith(GOVERNANCE_PREFIXES) for path in files)

    gaps: list[str] = []
    if not validated:
        gaps.append("checks_sem_sucesso_confirmado")
    if not check_links:
        gaps.append("check_url_ausente")
    if not raw.get("head_sha"):
        gaps.append("head_sha_ausente")
    if not raw.get("html_url"):
        gaps.append("pr_url_ausente")

    return {
        "number": int(raw.get("number", 0)),
        "title": str(raw.get("title") or ""),
        "url": str(raw.get("html_url") or ""),
        "merged_at": str(raw.get("merged_at") or ""),
        "head_sha": str(raw.get("head_sha") or ""),
        "files": files,
        "checks": [
            {
                "name": str(c.get("name") or ""),
                "status": str(c.get("status") or ""),
                "conclusion": str(c.get("conclusion") or ""),
                "url": str(c.get("html_url") or ""),
            }
            for c in checks
        ],
        "implemented": True,
        "validated": validated,
        "evidenced": evidenced,
        "consolidated": consolidated,
        "governed": governed,
        "evidence_gaps": gaps,
    }


def coverage(items: list[dict[str, Any]]) -> dict[str, float]:
    total = len(items)
    if total == 0:
        return {dimension: 0.0 for dimension in DIMENSIONS}
    return {
        dimension: round(100.0 * sum(bool(item.get(dimension)) for item in items) / total, 1)
        for dimension in DIMENSIONS
    }


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_items": len(items),
        "counts": {
            dimension: sum(bool(item.get(dimension)) for item in items)
            for dimension in DIMENSIONS
        },
        "coverage_percent": coverage(items),
    }


def compare_summary(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, int] | None:
    if not previous:
        return None
    previous_counts = previous.get("counts")
    if not isinstance(previous_counts, dict):
        return None
    return {
        dimension: int(current.get("counts", {}).get(dimension, 0))
        - int(previous_counts.get(dimension, 0))
        for dimension in DIMENSIONS
    }


def _mark(value: bool) -> str:
    return "sim" if value else "não"


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    perc = report["coverage_percent"]
    lines = [
        "# ReqSys — Log semanal de realizações",
        "",
        f"- Repositório: `{report['repository']}`",
        f"- Janela: `{report['window']['start']}` a `{report['window']['end']}`",
        f"- Gerado em: `{report['generated_at']}`",
        "",
        "## Resumo por evidência",
        "",
        "| Dimensão | Itens | Cobertura da janela |",
        "|---|---:|---:|",
    ]
    labels = {
        "implemented": "Implementado",
        "validated": "Validado",
        "evidenced": "Evidenciado",
        "consolidated": "Consolidado",
        "governed": "Governado",
    }
    for dimension in DIMENSIONS:
        lines.append(f"| {labels[dimension]} | {counts[dimension]} | {perc[dimension]:.1f}% |")

    lines += [
        "",
        "> Os percentuais acima representam **cobertura de evidência na janela analisada** e não representam percentual global de conclusão do ReqSys.",
        "",
        "## Mudança desde o log anterior",
        "",
    ]
    delta = report.get("delta_from_previous")
    if delta is None:
        lines.append("Baseline anterior não encontrado; esta execução estabelece o primeiro snapshot comparável.")
    else:
        for dimension in DIMENSIONS:
            value = int(delta[dimension])
            lines.append(f"- {labels[dimension]}: {value:+d}")

    lines += [
        "",
        "## Itens",
        "",
        "| PR | Implementado | Validado | Evidenciado | Consolidado | Governado |",
        "|---|---|---|---|---|---|",
    ]
    for item in report["items"]:
        link = f"[#{item['number']}]({item['url']})" if item["url"] else f"#{item['number']}"
        lines.append(
            f"| {link} — {item['title']} | {_mark(item['implemented'])} | "
            f"{_mark(item['validated'])} | {_mark(item['evidenced'])} | "
            f"{_mark(item['consolidated'])} | {_mark(item['governed'])} |"
        )
        lines.append(f"| ↳ SHA `{item['head_sha'][:12] or 'ausente'}` |  |  |  |  |  |")

    lines += ["", "## Evidências técnicas", ""]
    if not report["items"]:
        lines.append("Nenhuma Pull Request mesclada encontrada na janela.")
    else:
        for item in report["items"]:
            check_parts = []
            for check in item["checks"]:
                name = check["name"] or "check"
                conclusion = check["conclusion"] or check["status"] or "sem conclusão"
                if check["url"]:
                    check_parts.append(f"[{name}]({check['url']})={conclusion}")
                else:
                    check_parts.append(f"{name}={conclusion}")
            checks_text = "; ".join(check_parts) if check_parts else "checks não encontrados"
            lines.append(f"- PR #{item['number']} — SHA `{item['head_sha'] or 'ausente'}` — {checks_text}")

    gaps = [item for item in report["items"] if item["evidence_gaps"]]
    lines += ["", "## Pendências de evidência", ""]
    if not gaps:
        lines.append("Nenhuma lacuna automática detectada nesta janela.")
    else:
        for item in gaps:
            lines.append(
                f"- PR #{item['number']}: {', '.join(item['evidence_gaps'])}."
            )

    lines += [
        "",
        "## Critérios",
        "",
        "- **Implementado:** Pull Request mesclada na janela.",
        "- **Validado:** ao menos um check concluído com sucesso e nenhum check concluído em falha.",
        "- **Evidenciado:** PR, SHA do head e link de check disponíveis.",
        "- **Consolidado:** alteração em `CHANGELOG.md`, `docs/`, `audit/`, `evidence/` ou `reports/`.",
        "- **Governado:** validado e com alteração em `.sdd/`, `governance/`, `.github/workflows/` ou `config/`.",
        "",
    ]
    return "\n".join(lines)


def collect(client: GitHubClient, repo: str, start: str, end: str) -> list[dict[str, Any]]:
    query = quote(f"repo:{repo} is:pr is:merged merged:{start}..{end}")
    search = client.get(f"/search/issues?q={query}&sort=updated&order=asc&per_page=100")
    issues = search.get("items", [])
    if not isinstance(issues, list):
        raise GitHubApiError("Resposta de busca de PRs inválida")

    items: list[dict[str, Any]] = []
    for issue in issues:
        number = int(issue["number"])
        pr = client.get(f"/repos/{repo}/pulls/{number}")
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        files = client.paged(f"/repos/{repo}/pulls/{number}/files")
        checks: list[dict[str, Any]] = []
        if head_sha:
            check_payload = client.get(f"/repos/{repo}/commits/{head_sha}/check-runs?per_page=100")
            raw_checks = check_payload.get("check_runs", [])
            if not isinstance(raw_checks, list):
                raise GitHubApiError(f"Checks inválidos para PR #{number}")
            checks = [check for check in raw_checks if isinstance(check, dict)]
        items.append(
            classify_item(
                {
                    "number": number,
                    "title": pr.get("title"),
                    "html_url": pr.get("html_url"),
                    "merged_at": pr.get("merged_at"),
                    "head_sha": head_sha,
                    "files": [file.get("filename") for file in files if file.get("filename")],
                    "checks": checks,
                }
            )
        )
    return items


def load_previous(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--previous", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/reqsys-weekly-accomplishment-log"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if "/" not in args.repo:
        print("repository inválido/ausente", file=sys.stderr)
        return 2

    now = datetime.now(UTC)
    end = args.end or now.date().isoformat()
    start = args.start or (now.date() - timedelta(days=7)).isoformat()

    try:
        client = GitHubClient(
            os.environ.get("GITHUB_TOKEN", ""),
            os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        )
        items = collect(client, args.repo, start, end)
    except (ValueError, GitHubApiError) as exc:
        print(f"COLLECTION_FAILED: {exc}", file=sys.stderr)
        return 3

    summary = summarize(items)
    previous = load_previous(args.previous)
    report: dict[str, Any] = {
        "schema_version": 1,
        "repository": args.repo,
        "window": {"start": start, "end": end},
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        **summary,
        "delta_from_previous": None,
        "items": items,
    }
    report["delta_from_previous"] = compare_summary(report, previous)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "reqsys-weekly-accomplishment-log.json"
    md_path = args.output_dir / "reqsys-weekly-accomplishment-log.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(json.dumps({"result": "OK", "items": len(items), "json": str(json_path), "markdown": str(md_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
