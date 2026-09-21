#!/usr/bin/env python3
"""Materializa e valida consultas da base Kindle nos hosts DEV autorizados."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

CONFIRM = "MATERIALIZE-KINDLE-QUERIES"
ALLOWED_HOSTS = {"Noteri", "DESKTOP-PDQK954"}
CANONICAL_ROOT = Path(r"C:\dev\chatgpt-workers\kindle-knowledge-local")

QUERIES = [
    (
        "KND-20260812-001",
        "Quartis e percentis",
        """SELECT
    percentile_cont(0.25) WITHIN GROUP (ORDER BY mag) AS pct_25,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY mag) AS pct_50,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY mag) AS pct_75
FROM earthquakes
WHERE mag IS NOT NULL
  AND place = 'Central Alaska';""",
        ("percentile_cont", "within group", "order by mag"),
    ),
    (
        "KND-20260812-002",
        "Percentis em métricas diferentes",
        """SELECT
    percentile_cont(0.25) WITHIN GROUP (ORDER BY mag) AS pct_25_mag,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY depth) AS pct_25_depth
FROM earthquakes
WHERE mag IS NOT NULL
  AND place = 'Central Alaska';""",
        ("percentile_cont", "order by mag", "order by depth"),
    ),
    (
        "KND-20260812-003",
        "Z-score",
        """SELECT
    a.place,
    a.mag,
    b.avg_mag,
    b.std_dev,
    (a.mag - b.avg_mag) / b.std_dev AS z_score
FROM earthquakes AS a
CROSS JOIN (
    SELECT avg(mag) AS avg_mag, stddev_pop(mag) AS std_dev
    FROM earthquakes
    WHERE mag IS NOT NULL
) AS b
WHERE a.mag IS NOT NULL;""",
        ("stddev_pop", "z_score", "avg(mag)"),
    ),
    (
        "KND-20260815-001",
        "Box plot e IQR",
        """WITH stats AS (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY mag) AS q1,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY mag) AS median,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY mag) AS q3
    FROM earthquakes
    WHERE place LIKE '%Japan%'
)
SELECT
    q1,
    median,
    q3,
    (q3 - q1) * 1.5 AS iqr_1_5,
    q1 - (q3 - q1) * 1.5 AS lower_whisker,
    q3 + (q3 - q1) * 1.5 AS upper_whisker
FROM stats;""",
        ("percentile_cont", "lower_whisker", "upper_whisker"),
    ),
    (
        "KND-20260816-001",
        "Normalização geográfica",
        """SELECT
    CASE
        WHEN place LIKE '% of %' THEN split_part(place, ' of ', 2)
        ELSE place
    END AS place_name,
    count(*) AS records
FROM earthquakes
WHERE depth > 600
GROUP BY 1
ORDER BY 2 DESC;""",
        ("split_part", "group by 1", "depth > 600"),
    ),
    (
        "KND-20260816-002",
        "Capitalização inconsistente",
        """SELECT
    type,
    lower(type) AS normalized_type,
    type = lower(type) AS already_normalized,
    count(*) AS records
FROM earthquakes
GROUP BY 1, 2, 3
ORDER BY 2, 4 DESC;""",
        ("lower(type)", "group by 1, 2, 3", "already_normalized"),
    ),
    (
        "KND-20260818-001",
        "Limpeza de localização + agregação",
        """SELECT
    CASE
        WHEN place LIKE '% of %' THEN split_part(place, ' of ', 2)
        ELSE place
    END AS place,
    count(*) AS earthquakes
FROM earthquakes
WHERE mag >= 6
GROUP BY 1
ORDER BY 2 DESC;""",
        ("split_part", "mag >= 6", "count(*)"),
    ),
]


class MaterializeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_host(expected_host: str) -> str:
    if os.name != "nt":
        raise MaterializeError("Windows obrigatório")
    if expected_host not in ALLOWED_HOSTS:
        raise MaterializeError("host esperado não autorizado")
    actual = socket.gethostname()
    if actual.casefold() != expected_host.casefold():
        raise MaterializeError(f"host divergente: esperado={expected_host} observado={actual}")
    if str(os.environ.get("RUNNER_OS") or "").casefold() != "windows":
        raise MaterializeError("RUNNER_OS divergente")
    if not str(os.environ.get("RUNNER_NAME") or "").strip():
        raise MaterializeError("RUNNER_NAME ausente")
    return actual


def validate_output_root(path: Path) -> Path:
    resolved = path.resolve()
    canonical = CANONICAL_ROOT.resolve()
    if resolved != canonical:
        raise MaterializeError(f"output_root não autorizado: {resolved}")
    return resolved


def render_sql() -> str:
    parts = [
        "-- Kindle Knowledge - consultas locais",
        "-- Dialeto de referência: PostgreSQL compatível com ordered-set aggregates.",
        "-- Arquivo gerado; fonte versionada no GitHub.",
        "",
    ]
    for query_id, title, sql, _tokens in QUERIES:
        parts.extend([f"-- {query_id} | {title}", sql.strip(), ""])
    return "\n".join(parts).rstrip() + "\n"


def render_readme() -> str:
    return (
        "# Kindle Knowledge - consultas locais\n\n"
        "Cópia local para estudo e testes. A fonte versionada permanece no GitHub.\n\n"
        "- kindle_analysis_queries.sql: 7 consultas catalogadas.\n"
        "- manifest.json: hashes e metadados da materialização.\n"
        "- evidence.json: evidência sanitizada da última execução.\n"
    )


def validate_queries(sql_text: str) -> list[str]:
    lowered = sql_text.casefold()
    errors: list[str] = []
    for query_id, _title, _sql, tokens in QUERIES:
        if query_id.casefold() not in lowered:
            errors.append(f"{query_id}: marcador ausente")
        for token in tokens:
            if token.casefold() not in lowered:
                errors.append(f"{query_id}: token ausente: {token}")
    if sql_text.count(";") != len(QUERIES):
        errors.append("quantidade de statements divergente")
    return errors


def atomic_write(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
    return True


def materialize(expected_host: str, output_root: Path, correlation_id: str) -> dict:
    if not 8 <= len(correlation_id.strip()) <= 160:
        raise MaterializeError("correlation_id inválido")
    host = validate_host(expected_host)
    root = validate_output_root(output_root)
    queries_dir = root / "queries"
    sql_text = render_sql()
    errors = validate_queries(sql_text)
    if errors:
        raise MaterializeError("; ".join(errors))

    sql_path = queries_dir / "kindle_analysis_queries.sql"
    readme_path = queries_dir / "README.md"
    changed = {
        "kindle_analysis_queries.sql": atomic_write(sql_path, sql_text),
        "README.md": atomic_write(readme_path, render_readme()),
    }

    manifest = {
        "schema_version": 1,
        "host": host,
        "query_count": len(QUERIES),
        "sql_sha256": sha256_text(sql_text),
        "query_ids": [item[0] for item in QUERIES],
        "correlation_id": correlation_id,
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    changed["manifest.json"] = atomic_write(queries_dir / "manifest.json", manifest_text)

    observed = sql_path.read_text(encoding="utf-8")
    if sha256_text(observed) != manifest["sql_sha256"]:
        raise MaterializeError("leitura independente do SQL divergiu do manifest")

    return {
        "ok": True,
        "host": host,
        "root": str(root),
        "query_count": len(QUERIES),
        "sql_sha256": manifest["sql_sha256"],
        "changed_files": sorted(name for name, was_changed in changed.items() if was_changed),
        "correlation_id": correlation_id,
        "production_touched": False,
        "secrets_read": False,
        "observed_at": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_ROOT)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    code = 0
    try:
        if args.confirm != CONFIRM:
            raise MaterializeError("confirmação inválida")
        payload = materialize(args.expected_host, args.output_root, args.correlation_id)
    except (MaterializeError, OSError) as exc:
        payload = {
            "ok": False,
            "host": socket.gethostname(),
            "correlation_id": args.correlation_id,
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "production_touched": False,
            "secrets_read": False,
            "observed_at": utc_now(),
        }
        code = 2

    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
