#!/usr/bin/env python3
"""Evidence and governance helpers for the free-tier ReqSys backup workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ENVS = {"dev", "stg", "prod"}
CRITS = {"low", "medium", "high", "critical"}
REQ = {
    "id",
    "environment",
    "github_environment",
    "fly_app",
    "criticality",
    "enabled",
    "rpo_target_minutes",
    "rto_target_seconds",
    "rollout_state",
}
GIB = 1024**3


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        counts: dict[str, int] = {}
        names = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for (name,) in names:
            quoted = str(name).replace('"', '""')
            counts[str(name)] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
            )
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha(path),
        "quick_check": quick,
        "table_counts": counts,
        "table_count": len(counts),
        "row_count_total": sum(counts.values()),
    }


def validate_inventory(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    storage = payload.get("storage")
    defaults = payload.get("defaults")
    assets = payload.get("assets")

    if payload.get("schema_version") != "1.0.0":
        errors.append("schema_version must be 1.0.0")
    if not isinstance(storage, dict):
        errors.append("storage must be an object")
    if not isinstance(defaults, dict):
        errors.append("defaults must be an object")
    if not isinstance(assets, list) or not assets:
        return errors + ["assets must be a non-empty array"]

    ids: set[str] = set()
    envs: set[str] = set()
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            errors.append(f"assets[{index}] must be an object")
            continue
        missing = REQ - set(asset)
        if missing:
            errors.append(
                f"assets[{index}] missing fields: {', '.join(sorted(missing))}"
            )
            continue
        if asset["id"] in ids:
            errors.append(f"duplicate asset id: {asset['id']}")
        ids.add(asset["id"])
        envs.add(asset["environment"])
        if asset["environment"] not in ENVS:
            errors.append(f"assets[{index}].environment invalid")
        if asset["criticality"] not in CRITS:
            errors.append(f"assets[{index}].criticality invalid")
        if not isinstance(asset["enabled"], bool):
            errors.append(f"assets[{index}].enabled must be boolean")
        if not str(asset["fly_app"]).startswith("reqsys-api"):
            errors.append(f"assets[{index}].fly_app outside allowlist")
        for key in ("rpo_target_minutes", "rto_target_seconds"):
            if not isinstance(asset[key], int) or asset[key] <= 0:
                errors.append(f"assets[{index}].{key} must be positive")

    if envs != ENVS:
        errors.append("inventory must contain exactly dev, stg and prod")
    if isinstance(storage, dict):
        warn = storage.get("free_tier_warn_bytes")
        hard = storage.get("free_tier_hard_bytes")
        if (
            not isinstance(warn, int)
            or not isinstance(hard, int)
            or not 0 < warn < hard
        ):
            errors.append("free-tier quota thresholds invalid")
    return errors


def merged(payload: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    defaults = dict(payload.get("defaults", {}))
    retention = dict(defaults.pop("retention", {}))
    result = {**defaults, **asset}
    result["retention"] = {**retention, **asset.get("retention", {})}
    return result


def select(
    payload: dict[str, Any],
    target: str,
    include_disabled: bool,
) -> list[dict[str, Any]]:
    return [
        merged(payload, asset)
        for asset in payload["assets"]
        if (target == "all" or asset["environment"] == target)
        and (asset["enabled"] or include_disabled)
    ]


def quota(total: int, warn: int, hard: int) -> dict[str, Any]:
    status = "critical" if total >= hard else "warning" if total >= warn else "healthy"
    return {
        "status": status,
        "total_size_bytes": total,
        "warn_bytes": warn,
        "hard_bytes": hard,
        "utilization_percent": round(total / hard * 100, 3),
    }


def restic_size(payload: Any) -> int:
    if isinstance(payload, dict):
        for key in ("total_size", "total_blob_size", "total_uncompressed_size"):
            if isinstance(payload.get(key), int):
                return payload[key]
    raise ValueError("restic stats JSON missing total size")


def public(manifest_payload: dict[str, Any]) -> dict[str, Any]:
    counts = manifest_payload.get("table_counts", {})
    canonical = json.dumps(counts, sort_keys=True, separators=(",", ":"))
    return {
        "size_bytes": manifest_payload.get("size_bytes"),
        "sha256": manifest_payload.get("sha256"),
        "quick_check": manifest_payload.get("quick_check"),
        "table_count": manifest_payload.get("table_count", len(counts)),
        "row_count_total": manifest_payload.get("row_count_total"),
        "table_counts_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def evidence(
    asset: dict[str, Any],
    source: dict[str, Any],
    restored: dict[str, Any],
    quota_payload: dict[str, Any],
    snapshot_id: str,
    run_url: str,
    correlation_id: str,
    started_at: str,
    completed_at: str,
    rto: float,
) -> dict[str, Any]:
    match = (
        source.get("quick_check") == restored.get("quick_check") == "ok"
        and source.get("sha256") == restored.get("sha256")
        and source.get("table_counts") == restored.get("table_counts")
    )
    try:
        rpo = max(
            0.0,
            (
                iso(completed_at) - iso(str(source.get("generated_at")))
            ).total_seconds()
            / 60,
        )
    except (TypeError, ValueError):
        rpo = 0.0

    passed = (
        match
        and rpo <= asset["rpo_target_minutes"]
        and rto <= asset["rto_target_seconds"]
        and quota_payload["status"] != "critical"
    )
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-04",
        "evidence_class": "real_asset_external_encrypted_backup_restore",
        "asset_id": asset["id"],
        "environment": asset["environment"],
        "fly_app": asset["fly_app"],
        "database_engine": asset["database_engine"],
        "storage_provider": "cloudflare-r2",
        "encryption": "restic-client-side",
        "snapshot_id": snapshot_id,
        "backup_started_at": started_at,
        "restore_completed_at": completed_at,
        "rpo_minutes": round(rpo, 6),
        "rpo_target_minutes": asset["rpo_target_minutes"],
        "rto_seconds": round(rto, 6),
        "rto_target_seconds": asset["rto_target_seconds"],
        "integrity_match": match,
        "source_manifest": public(source),
        "restored_manifest": public(restored),
        "quota": quota_payload,
        "production_read_only": asset["environment"] == "prod",
        "production_restore_claimed": False,
        "correlation_id": correlation_id,
        "run_url": run_url,
        "result": "passed" if passed else "failed",
        "generated_at": now(),
    }


def dashboard(
    inventory: dict[str, Any],
    items: list[dict[str, Any]],
    configured: bool,
    missing: list[str],
    run_url: str,
    execution_result: str,
) -> dict[str, Any]:
    by_asset = {item.get("asset_id"): item for item in items}
    rows: list[dict[str, Any]] = []

    for raw_asset in inventory["assets"]:
        asset = merged(inventory, raw_asset)
        item = by_asset.get(asset["id"])
        if item:
            status = "healthy" if item.get("result") == "passed" else "critical"
        elif asset["enabled"] and not configured:
            status = "blocked_configuration"
        elif asset["enabled"] and execution_result in {"failure", "cancelled"}:
            status = "critical"
        elif asset["enabled"]:
            status = "pending_execution"
        else:
            status = "rollout_pending"

        rows.append(
            {
                "asset_id": asset["id"],
                "environment": asset["environment"],
                "fly_app": asset["fly_app"],
                "enabled": asset["enabled"],
                "rollout_state": asset["rollout_state"],
                "status": status,
                "result": item.get("result") if item else None,
                "integrity_match": item.get("integrity_match") if item else None,
                "rpo_minutes": item.get("rpo_minutes") if item else None,
                "rto_seconds": item.get("rto_seconds") if item else None,
                "snapshot_id": item.get("snapshot_id") if item else None,
                "quota": item.get("quota") if item else None,
                "correlation_id": item.get("correlation_id") if item else None,
            }
        )

    health = (
        "critical"
        if any(row["status"] == "critical" for row in rows)
        else "warning"
        if any(row["status"] != "healthy" for row in rows)
        else "healthy"
    )
    storage = inventory.get("storage") or {}
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-04",
        "health": health,
        "generated_at": now(),
        "external_storage_configured": configured,
        "missing_secrets": missing,
        "run_url": run_url,
        "execution_result": execution_result,
        "quota_thresholds": {
            "warn_bytes": storage.get("free_tier_warn_bytes"),
            "hard_bytes": storage.get("free_tier_hard_bytes"),
        },
        "assets": rows,
    }


def _gib(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "não configurado"
    gib = value / GIB
    return f"{gib:g} GiB"


def markdown(payload: dict[str, Any]) -> str:
    icon = {"healthy": "🟢", "warning": "🟡", "critical": "🔴"}[payload["health"]]
    lines = [
        f"# {icon} Dashboard BACEN-04 — Cobertura real de backup",
        "",
        f"> Atualizado automaticamente em `{payload['generated_at']}`.",
        "",
        "- Armazenamento externo configurado: "
        f"**{str(payload['external_storage_configured']).lower()}**",
    ]
    if payload["missing_secrets"]:
        lines.append(
            f"- Configuração pendente: `{', '.join(payload['missing_secrets'])}`"
        )

    lines += [
        "",
        "| Ambiente | Ativo | Estado | Resultado | Integridade | RPO | RTO | Rollout |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for item in payload["assets"]:
        lines.append(
            f"| {item['environment'].upper()} | `{item['asset_id']}` | "
            f"**{item['status']}** | `{item['result'] or '—'}` | "
            f"`{'sim' if item['integrity_match'] is True else '—'}` | "
            f"`{str(item['rpo_minutes']) + ' min' if item['rpo_minutes'] is not None else '—'}` | "
            f"`{str(item['rto_seconds']) + ' s' if item['rto_seconds'] is not None else '—'}` | "
            f"{item['rollout_state']} |"
        )

    quota_thresholds = payload.get("quota_thresholds") or {}
    warn = _gib(quota_thresholds.get("warn_bytes"))
    hard = _gib(quota_thresholds.get("hard_bytes"))
    return "\n".join(
        lines
        + [
            "",
            "## Guard rails gratuitos",
            "",
            "- dumps nunca são gravados no repositório ou na issue;",
            "- criptografia ocorre no cliente antes do armazenamento externo;",
            f"- quota alerta em {warn} e bloqueia em {hard};",
            "- PROD permanece desabilitado até evidência válida em DEV e STG;",
            "- restaurações ocorrem fora do ambiente de origem.",
            "",
            f"[Abrir execução]({payload['run_url']})",
            "",
        ]
    )


def card(payload: dict[str, Any]) -> dict[str, Any]:
    color = {
        "healthy": "Good",
        "warning": "Warning",
        "critical": "Attention",
    }[payload["health"]]
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "msteams": {"width": "Full"},
        "body": [
            {
                "type": "TextBlock",
                "text": "ReqSys — cobertura real de backup",
                "weight": "Bolder",
                "size": "Large",
                "color": color,
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"Saúde: {payload['health']}",
                "wrap": True,
            },
            {
                "type": "FactSet",
                "facts": [
                    {
                        "title": item["environment"].upper(),
                        "value": f"{item['status']} · {item['asset_id']}",
                    }
                    for item in payload["assets"]
                ],
            },
        ],
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "Abrir execução",
                "url": payload["run_url"],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--inventory", type=Path, required=True)

    matrix_parser = subparsers.add_parser("matrix")
    matrix_parser.add_argument("--inventory", type=Path, required=True)
    matrix_parser.add_argument(
        "--target",
        choices=["dev", "stg", "prod", "all"],
        default="all",
    )
    matrix_parser.add_argument("--include-disabled", action="store_true")

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("--database", type=Path, required=True)
    manifest_parser.add_argument("--output", type=Path, required=True)

    quota_parser = subparsers.add_parser("quota")
    quota_parser.add_argument("--stats", type=Path, required=True)
    quota_parser.add_argument("--warn", type=int, required=True)
    quota_parser.add_argument("--hard", type=int, required=True)
    quota_parser.add_argument("--output", type=Path, required=True)

    evidence_parser = subparsers.add_parser("evidence")
    for name in ("asset", "source", "restored", "quota", "output"):
        evidence_parser.add_argument(f"--{name}", type=Path, required=True)
    for name in (
        "snapshot-id",
        "run-url",
        "correlation-id",
        "started-at",
        "completed-at",
    ):
        evidence_parser.add_argument(f"--{name}", required=True)
    evidence_parser.add_argument("--rto", type=float, required=True)

    dashboard_parser = subparsers.add_parser("dashboard")
    dashboard_parser.add_argument("--inventory", type=Path, required=True)
    dashboard_parser.add_argument("--evidence-dir", type=Path, required=True)
    dashboard_parser.add_argument("--configured", action="store_true")
    dashboard_parser.add_argument("--missing", default="")
    dashboard_parser.add_argument("--run-url", required=True)
    dashboard_parser.add_argument("--execution-result", default="unknown")
    dashboard_parser.add_argument("--json", type=Path, required=True)
    dashboard_parser.add_argument("--markdown", type=Path, required=True)
    dashboard_parser.add_argument("--card", type=Path, required=True)

    args = parser.parse_args()

    if args.cmd == "validate":
        errors = validate_inventory(read(args.inventory))
        print("\n".join(errors) if errors else "inventory valid")
        return bool(errors)

    if args.cmd == "matrix":
        inventory = read(args.inventory)
        errors = validate_inventory(inventory)
        if errors:
            raise SystemExit("; ".join(errors))
        print(
            json.dumps(
                {"include": select(inventory, args.target, args.include_disabled)},
                separators=(",", ":"),
            )
        )
        return 0

    if args.cmd == "manifest":
        write(args.output, manifest(args.database))
        return 0

    if args.cmd == "quota":
        result = quota(
            restic_size(read(args.stats)),
            args.warn,
            args.hard,
        )
        write(args.output, result)
        print(result["status"])
        return 2 if result["status"] == "critical" else 0

    if args.cmd == "evidence":
        result = evidence(
            read(args.asset),
            read(args.source),
            read(args.restored),
            read(args.quota),
            args.snapshot_id,
            args.run_url,
            args.correlation_id,
            args.started_at,
            args.completed_at,
            args.rto,
        )
        write(args.output, result)
        print(result["result"])
        return result["result"] != "passed"

    items = (
        [read(path) for path in args.evidence_dir.rglob("evidence.json")]
        if args.evidence_dir.is_dir()
        else []
    )
    result = dashboard(
        read(args.inventory),
        items,
        args.configured,
        [item for item in args.missing.split(",") if item],
        args.run_url,
        args.execution_result,
    )
    write(args.json, result)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(result), encoding="utf-8")
    write(args.card, card(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
