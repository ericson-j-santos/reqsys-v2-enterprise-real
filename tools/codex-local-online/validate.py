from pathlib import Path

base = Path(__file__).resolve().parent
html = (base / "index.html").read_text(encoding="utf-8")
markers = [
    "ReqSys Codex Online",
    "correlation_id",
    "Guard rails ativos",
    "payload ReqSys",
    "/v1/codex/analyze",
    "Usar JWT da sessão",
    "Verificar status",
]
missing = []
for marker in markers:
    if marker not in html:
        missing.append(marker)
if missing:
    raise SystemExit("Marcadores obrigatorios ausentes: " + ", ".join(missing))
if "function mock" not in html:
    raise SystemExit("Fluxo principal nao encontrado")
continue_cfg = base.parent.parent / "infra" / "codex-local" / "continue" / "config.yaml"
if not continue_cfg.is_file():
    raise SystemExit("Config Continue ausente: " + str(continue_cfg))
runbook = base.parent.parent / "docs" / "runbooks" / "codex-vscode-local-inicio-rapido.md"
if not runbook.is_file():
    raise SystemExit("Runbook inicio rapido ausente: " + str(runbook))
print("codex-local-online: validacao estatica OK")
