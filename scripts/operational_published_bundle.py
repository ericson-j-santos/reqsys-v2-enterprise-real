#!/usr/bin/env python3
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

FILES = [
    ("center.html", Path("artifacts/operational-center/index.html"), "Operational Center"),
    ("history.html", Path("artifacts/operational-history/operational-history.html"), "Operational History"),
    ("artifact-index.html", Path("artifacts/operational-index/index.html"), "Artifact Index"),
    ("hub.json", Path("artifacts/operational-intelligence-hub/operational-intelligence-hub.json"), "Operational Hub JSON"),
    ("history.json", Path("artifacts/operational-history/operational-history.json"), "Operational History JSON"),
    ("history-trend.json", Path("artifacts/operational-history/operational-history-trend.json"), "Operational Trend JSON"),
]

TEMPLATE = """<!doctype html>
<html lang='pt-BR'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>ReqSys Operational Published Bundle</title>
<style>
body{{margin:0;background:#0f172a;color:#e5e7eb;font-family:Arial,Helvetica,sans-serif}}
main{{max-width:1100px;margin:auto;padding:24px}}
.card{{background:#111827;border:1px solid #374151;border-radius:16px;padding:18px;margin-top:16px}}
a{{color:#60a5fa;text-decoration:none;font-weight:700}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;border-bottom:1px solid #374151;text-align:left}}th{{color:#9ca3af}}
.badge{{display:inline-block;padding:6px 10px;border-radius:999px;background:#2563eb;color:white;font-size:12px}}
</style>
</head>
<body><main>
<h1>ReqSys Operational Published Bundle</h1>
<p>Pacote operacional navegável, autocontido e pronto para publicação futura controlada.</p>
<div class='card'><span class='badge'>Zero-CDN</span> <span class='badge'>Artifact auditável</span> <span class='badge'>Sem deploy automático</span></div>
<div class='card'>
<table><thead><tr><th>Recurso</th><th>Arquivo</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>
</div>
<div class='card'>Gerado em UTC: {generated}</div>
</main></body></html>
"""


def main() -> int:
    out_dir = Path("artifacts/operational-published-bundle")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for target, source, label in FILES:
        if source.exists():
            shutil.copyfile(source, out_dir / target)
            status = "copiado"
            link = f"<a href='{target}'>{target}</a>"
        else:
            status = "ausente"
            link = target
        rows.append(f"<tr><td>{label}</td><td>{link}</td><td>{status}</td></tr>")
    index = TEMPLATE.format(rows="".join(rows), generated=datetime.now(timezone.utc).isoformat())
    (out_dir / "index.html").write_text(index, encoding="utf-8")
    print("Operational published bundle generated.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
