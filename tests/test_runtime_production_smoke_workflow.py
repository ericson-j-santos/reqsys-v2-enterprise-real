"""Contrato: PR valida código; smoke publicado exige runtime explícito."""
import re
from pathlib import Path

import yaml


def test_smoke_workflow_separa_pr_de_runtime_publicado_sem_fallback():
    text = Path(".github/workflows/runtime-production-smoke-governed.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    steps = workflow["jobs"]["runtime-production-smoke"]["steps"]
    validation = next(step for step in steps if step.get("name") == "Validar script e testes do smoke")
    live = next(step for step in steps if step.get("name") == "Executar smoke público governado")
    assert "if" not in validation
    assert "test_runtime_production_smoke_governed.py" in validation["run"]
    assert live["if"] == "github.event_name != 'pull_request'"
    assert "vars.RUNTIME_PUBLIC_BASE_URL" in live["env"]["RUNTIME_PUBLIC_BASE_URL"]
    assert 'if [[ -z "${RUNTIME_PUBLIC_BASE_URL}" ]]' in live["run"]
    assert "exit 1" in live["run"]
    assert "*fly.io*|*fly.dev*" in live["run"]
    assert "https://reqsys-app.fly.dev" not in text
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
