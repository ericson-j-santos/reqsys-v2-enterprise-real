from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKERS = ("frontend-angular", "frontend-vuetify")
STATIC_FILES = (
    "playwright.config.ts",
    "package.json",
    "scripts/validar_qualidade.sh",
)


def operational_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    files = [repo_root / item for item in STATIC_FILES]
    workflows = repo_root / ".github" / "workflows"
    if workflows.exists():
        files.extend(sorted(workflows.glob("*.yml")))
        files.extend(sorted(workflows.glob("*.yaml")))
    return files


def find_references(repo_root: Path = REPO_ROOT) -> list[str]:
    results: list[str] = []
    for path in operational_files(repo_root):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(repo_root).as_posix()
        for marker in MARKERS:
            if marker in text:
                results.append(f"{relative}: {marker}")
    return results


def main() -> int:
    results = find_references()
    if results:
        print("Referências operacionais legadas encontradas:", file=sys.stderr)
        for item in results:
            print(f"- {item}", file=sys.stderr)
        return 1
    print("Nenhuma referência operacional a frontends legados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
