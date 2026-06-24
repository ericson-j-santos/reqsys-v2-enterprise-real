#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ARTIFACTS = [
    ("Operational Center", "artifacts/operational-center/index.html"),
    ("Operational History", "artifacts/operational-history/operational-history.html"),
    ("Operational Hub JSON", "artifacts/operational-intelligence-hub/operational-intelligence-hub.json"),
    ("Operational History JSON", "artifacts/operational-history/operational-history.json"),
]

HTML = """<!doctype html>
<html lang='pt-BR'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>ReqSys Operational Artifact Index</title>
<style>
body{margin:0;background:#0f172a;color:#e5e7eb;font-family:Arial,Helvetica,sans-serif}
main{max-width:1000px;margin:auto;padding:24px}
.card{background:#111827;border:1px solid #374151;border-radius:16px;padding:18px;margin-top:16px}
a{color:#60a5fa;text-decoration:none}table{width:100%;border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #374151;text-align:left}th{color:#9ca3af}
</style>
</head>
<body>
<main>
<h1>ReqSys Operational Artifact Index</h1>
<p>Indice operacional consolidado para navegacao dos artifacts HTML e JSON.</p>
<div class='card'>
<table>
<thead><tr><th>Artifact</th><th>Caminho</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
<div class='card'>Gerado em UTC: {generated}</div>
</main>
</body>
</html>
"""


def main() -> int:
    out_dir = Path('artifacts/operational-index')
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, path in ARTIFACTS:
        rows.append(f"<tr><td>{name}</td><td><code>{path}</code></td></tr>")
    html = HTML.format(rows=''.join(rows), generated=datetime.now(timezone.utc).isoformat())
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    print('Operational artifact index generated.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
