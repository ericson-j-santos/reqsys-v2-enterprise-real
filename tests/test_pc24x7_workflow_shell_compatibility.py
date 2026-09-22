from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def test_pc24x7_workflows_do_not_require_unprovisioned_pwsh():
    offending = []
    inspected = []
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        if "pc24x7" not in text or "runs-on:" not in text:
            continue
        inspected.append(path.name)
        if "shell: pwsh" in text:
            offending.append(path.name)

    assert inspected, "Nenhum workflow PC24x7 encontrado para validar"
    assert not offending, (
        "Workflows PC24x7 dependem de pwsh não provisionado no host: "
        + ", ".join(offending)
    )
