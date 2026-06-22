from pathlib import Path

base = Path(__file__).resolve().parent
html = (base / "index.html").read_text(encoding="utf-8")
markers = ["ReqSys Codex Online", "correlation_id", "Guard rails ativos", "GitHub Pages", "Payload ReqSys"]
missing = []
for marker in markers:
    if marker not in html:
        missing.append(marker)
if missing:
    raise SystemExit("Marcadores obrigatorios ausentes: " + ", ".join(missing))
if "function mock" not in html:
    raise SystemExit("Fluxo principal nao encontrado")
print("codex-local-online: validacao estatica OK")
