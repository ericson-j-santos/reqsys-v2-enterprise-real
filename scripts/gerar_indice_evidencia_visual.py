#!/usr/bin/env python3
"""Gera índice HTML navegável a partir de screenshots de evidência visual E2E."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path


def load_meta(png_path: Path) -> dict:
    meta_path = png_path.with_suffix('.json')
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}


def collect_screenshots(root: Path) -> list[dict]:
    items: list[dict] = []
    for png in sorted(root.rglob('*.png')):
        rel = png.relative_to(root).as_posix()
        meta = load_meta(png)
        items.append({
            'rel_path': rel,
            'name': meta.get('name') or png.stem,
            'url': meta.get('url', ''),
            'captured_at': meta.get('captured_at', ''),
            'metadata': {k: v for k, v in meta.items() if k not in {'name', 'url', 'captured_at', 'slug', 'viewport'}},
        })
    return items


def render_html(root: Path, items: list[dict], title: str) -> str:
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    cards = []
    for item in items:
        meta_bits = []
        if item['url']:
            meta_bits.append(f"<div><strong>URL:</strong> {escape(item['url'])}</div>")
        if item['captured_at']:
            meta_bits.append(f"<div><strong>Capturado:</strong> {escape(item['captured_at'])}</div>")
        for key, value in item['metadata'].items():
            meta_bits.append(f"<div><strong>{escape(str(key))}:</strong> {escape(str(value))}</div>")
        meta_html = ''.join(meta_bits)
        cards.append(
            f"""
            <article class="card">
              <h2>{escape(item['name'])}</h2>
              <p class="path">{escape(item['rel_path'])}</p>
              <img src="{escape(item['rel_path'])}" alt="{escape(item['name'])}" loading="lazy" />
              <div class="meta">{meta_html}</div>
            </article>
            """
        )

    body = '\n'.join(cards) if cards else '<p>Nenhuma evidência encontrada.</p>'
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1220;
      --card: #111a2e;
      --text: #e8eefc;
      --muted: #9fb0d0;
      --accent: #f39200;
    }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
    }}
    h1 {{ margin-top: 0; }}
    .summary {{ color: var(--muted); margin-bottom: 24px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      padding: 16px;
    }}
    .card h2 {{
      margin: 0 0 8px;
      font-size: 1rem;
      color: var(--accent);
    }}
    .path {{
      color: var(--muted);
      font-size: 0.85rem;
      word-break: break-all;
    }}
    img {{
      width: 100%;
      border-radius: 8px;
      margin: 12px 0;
      border: 1px solid rgba(255,255,255,0.06);
      background: #000;
    }}
    .meta {{
      font-size: 0.85rem;
      color: var(--muted);
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p class="summary">{len(items)} captura(s) em <code>{escape(str(root))}</code> — gerado em {generated}</p>
  <section class="grid">
    {body}
  </section>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--evidence-dir',
        default='frontend/test-results/evidence',
        help='Diretório raiz com PNGs e metadados JSON',
    )
    parser.add_argument(
        '--output',
        default='',
        help='Arquivo HTML de saída (default: <evidence-dir>/index.html)',
    )
    parser.add_argument('--title', default='ReqSys — Evidência Visual E2E')
    args = parser.parse_args()

    root = Path(args.evidence_dir).resolve()
    if not root.exists():
        print(f'Diretório inexistente: {root}')
        return 1

    items = collect_screenshots(root)
    output = Path(args.output) if args.output else root / 'index.html'
    output.write_text(render_html(root, items, args.title), encoding='utf-8')
    print(f'Índice gerado: {output} ({len(items)} imagens)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
