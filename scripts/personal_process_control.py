#!/usr/bin/env python3
"""Personal Process Control v1.2 - fila governada de pendencias."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape

OPEN_STATUSES = {
    "Detectada",
    "Triada",
    "Pronta para execucao",
    "Em execucao",
    "Aguardando evidencia",
    "Bloqueada externamente",
}
ACTIONABLE_STATUSES = {"Pronta para execucao", "Em execucao", "Aguardando evidencia"}
ACTIVE_STATUSES = {"Em execucao", "Aguardando evidencia"}
TERMINAL_STATUSES = {"Concluido", "Cancelado", "Duplicada"}
ALL_STATUSES = OPEN_STATUSES | TERMINAL_STATUSES
BLOCKER_TYPES = {"Nenhum", "Humano", "Tecnico", "Externo"}
VERSION = "1.2.0"
HISTORY_LIMIT_DAYS = 365
WIP_LIMIT = 3
AGING_ATTENTION_DAYS = 7
AGING_ESCALATE_DAYS = 14
AGING_CRITICAL_DAYS = 30
RECURRENCE_AUTOMATION_CYCLES = 3


def load_json(path: Path) -> Any:
    if not path.exists():
        raise ValueError(f"Arquivo obrigatorio ausente: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido em {path}: {exc}") from exc


def load_optional_history(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    value = load_json(path)
    if not isinstance(value, list):
        raise ValueError("historico: esperado array JSON")
    return [x for x in value if isinstance(x, dict)]


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def require_text(item, field, context, errors):
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}: campo '{field}' obrigatorio")
        return ""
    return value.strip()


def require_score(item, field, context, errors, minimum=1, maximum=5):
    value = item.get(field)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < minimum
        or value > maximum
    ):
        errors.append(
            f"{context}: campo '{field}' deve estar entre {minimum} e {maximum}"
        )
        return 0.0
    return float(value)


def parse_iso_date(value: Any, field: str, context: str, errors) -> date | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}: campo '{field}' obrigatorio")
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        errors.append(f"{context}: campo '{field}' deve usar YYYY-MM-DD")
        return None


def validate_unique_ids(items, collection, errors):
    seen = set()
    for index, item in enumerate(items, 1):
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            errors.append(f"{collection}[{index}]: campo 'id' obrigatorio")
        elif item_id in seen:
            errors.append(f"{collection}: id duplicado '{item_id}'")
        else:
            seen.add(item_id)


def validate_demands(items):
    errors = []
    if not isinstance(items, list):
        return ["demandas: esperado array JSON"]

    dict_items = [x for x in items if isinstance(x, dict)]
    if len(dict_items) != len(items):
        errors.append("demandas: todos os itens devem ser objetos")
    validate_unique_ids(dict_items, "demandas", errors)
    ids = {str(x.get("id", "")).strip() for x in dict_items}
    active_count = 0

    for item in dict_items:
        ctx = f"demanda {item.get('id', '?')}"
        for field in ("titulo", "area", "problema", "origem"):
            require_text(item, field, ctx, errors)

        parse_iso_date(item.get("estado_evidenciado_em"), "estado_evidenciado_em", ctx, errors)
        parse_iso_date(item.get("ultima_movimentacao_em"), "ultima_movimentacao_em", ctx, errors)

        impact = require_score(item, "impacto", ctx, errors)
        effort = require_score(item, "esforco", ctx, errors)
        frequency = require_score(item, "frequencia", ctx, errors)
        if effort == 0 and (impact or frequency):
            errors.append(f"{ctx}: esforco nao pode ser zero")

        status = require_text(item, "status", ctx, errors)
        if status and status not in ALL_STATUSES:
            errors.append(f"{ctx}: status invalido '{status}'")
        if status in ACTIVE_STATUSES:
            active_count += 1

        blocker = str(item.get("tipo_bloqueio", "Nenhum")).strip() or "Nenhum"
        if blocker not in BLOCKER_TYPES:
            errors.append(f"{ctx}: tipo_bloqueio invalido '{blocker}'")

        if status in OPEN_STATUSES:
            if not str(item.get("proxima_acao", "")).strip():
                errors.append(f"{ctx}: item aberto sem proxima_acao")
            if not str(item.get("criterio_conclusao", "")).strip():
                errors.append(f"{ctx}: item aberto sem criterio_conclusao")

        if status == "Concluido":
            if not str(item.get("criterio_conclusao", "")).strip():
                errors.append(f"{ctx}: concluido sem criterio_conclusao")
            if not str(item.get("evidencia", "")).strip():
                errors.append(f"{ctx}: concluido sem evidencia")

        if status == "Bloqueada externamente":
            if blocker == "Nenhum":
                errors.append(f"{ctx}: bloqueada externamente sem tipo_bloqueio")
            if not str(item.get("responsavel_bloqueio", "")).strip():
                errors.append(f"{ctx}: bloqueada externamente sem responsavel_bloqueio")

        dependencies = item.get("dependencias", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(dep, str) and dep.strip() for dep in dependencies
        ):
            errors.append(f"{ctx}: dependencias deve ser array de IDs")
        else:
            normalized = [dep.strip() for dep in dependencies]
            if len(normalized) != len(set(normalized)):
                errors.append(f"{ctx}: dependencias duplicadas")
            for dep in normalized:
                if dep == str(item.get("id", "")).strip():
                    errors.append(f"{ctx}: nao pode depender de si mesma")
                elif dep not in ids:
                    errors.append(f"{ctx}: dependencia inexistente '{dep}'")

        duplicate_of = str(item.get("duplicado_de", "")).strip()
        if status == "Duplicada":
            if not duplicate_of:
                errors.append(f"{ctx}: duplicada sem duplicado_de")
            elif duplicate_of not in ids:
                errors.append(f"{ctx}: duplicado_de inexistente '{duplicate_of}'")
            elif duplicate_of == str(item.get("id", "")).strip():
                errors.append(f"{ctx}: duplicado_de nao pode referenciar o proprio item")
        elif duplicate_of:
            errors.append(f"{ctx}: duplicado_de so e permitido no status Duplicada")

    if active_count > WIP_LIMIT:
        errors.append(
            f"demandas: WIP excedido ({active_count}/{WIP_LIMIT}) nos estados ativos"
        )
    return errors


def validate_library(items):
    errors = []
    if not isinstance(items, list):
        return ["biblioteca: esperado array JSON"]
    dict_items = [x for x in items if isinstance(x, dict)]
    validate_unique_ids(dict_items, "biblioteca", errors)
    for item in dict_items:
        ctx = f"componente {item.get('id', '?')}"
        for field in ("nome", "tipo", "area", "problema_resolvido", "versao", "status"):
            require_text(item, field, ctx, errors)
    return errors


def validate_automations(items):
    errors = []
    if not isinstance(items, list):
        return ["automacoes: esperado array JSON"]
    dict_items = [x for x in items if isinstance(x, dict)]
    validate_unique_ids(dict_items, "automacoes", errors)
    for item in dict_items:
        ctx = f"automacao {item.get('id', '?')}"
        for field in ("tarefa", "area", "status", "proxima_acao"):
            require_text(item, field, ctx, errors)
        require_score(item, "frequencia", ctx, errors)
        require_score(item, "impacto", ctx, errors)
        effort = require_score(item, "esforco_automacao", ctx, errors)
        minutes = item.get("tempo_manual_min")
        if (
            not isinstance(minutes, (int, float))
            or isinstance(minutes, bool)
            or minutes < 0
        ):
            errors.append(f"{ctx}: tempo_manual_min deve ser >= 0")
        if effort == 0:
            errors.append(f"{ctx}: esforco_automacao nao pode ser zero")
    return errors


def aging_days(item: dict[str, Any], as_of: date) -> int:
    moved = date.fromisoformat(str(item["ultima_movimentacao_em"]))
    return max(0, (as_of - moved).days)


def aging_level(days: int) -> str:
    if days > AGING_CRITICAL_DAYS:
        return "critico"
    if days > AGING_ESCALATE_DAYS:
        return "escalar"
    if days > AGING_ATTENTION_DAYS:
        return "atencao"
    return "normal"


def aging_urgency(days: int) -> int:
    if days > AGING_CRITICAL_DAYS:
        return 5
    if days > AGING_ESCALATE_DAYS:
        return 4
    if days > AGING_ATTENTION_DAYS:
        return 3
    if days > 3:
        return 2
    return 1


def dependency_unlock_factor(
    item_id: str, items: list[dict[str, Any]]
) -> int:
    dependents = sum(
        1
        for item in items
        if item.get("status") in OPEN_STATUSES
        and item_id in [str(x).strip() for x in item.get("dependencias", [])]
    )
    return min(5, 1 + dependents)


def demand_score(item, all_items=None, as_of: date | None = None):
    all_items = all_items or [item]
    as_of = as_of or date.today()
    days = aging_days(item, as_of)
    unlock = dependency_unlock_factor(str(item["id"]), all_items)
    urgency = max(int(float(item["frequencia"])), aging_urgency(days))
    return round(
        (float(item["impacto"]) * unlock * urgency) / float(item["esforco"]),
        4,
    )


def automation_score(item):
    return round(
        (
            float(item["frequencia"])
            * float(item["tempo_manual_min"])
            * float(item["impacto"])
        )
        / float(item["esforco_automacao"]),
        4,
    )


def priority(score):
    if score >= 40:
        return "P0 - Critica"
    if score >= 15:
        return "P1 - Alta"
    if score >= 5:
        return "P2 - Media"
    return "P3 - Baixa"


def pareto(items, score_fn: Callable):
    scored = [{**item, "indice": score_fn(item)} for item in items]
    scored.sort(key=lambda x: (-x["indice"], str(x.get("id", ""))))
    total = sum(x["indice"] for x in scored)
    cumulative = 0.0
    result = []
    reached = False
    for item in scored:
        cumulative += item["indice"]
        pct = 0.0 if total <= 0 else round(cumulative / total * 100, 2)
        critical = not reached
        result.append(
            {
                **item,
                "percentual_acumulado": pct,
                "faixa_pareto": "prioritario" if critical else "cauda",
            }
        )
        if pct >= 80:
            reached = True
    return result


def enrich_demand(
    item: dict[str, Any],
    all_items: list[dict[str, Any]],
    as_of: date,
) -> dict[str, Any]:
    days = aging_days(item, as_of)
    enriched = {
        **item,
        "aging_dias": days,
        "aging_nivel": aging_level(days),
        "fator_desbloqueio": dependency_unlock_factor(str(item["id"]), all_items),
        "fator_urgencia": max(int(float(item["frequencia"])), aging_urgency(days)),
    }
    enriched["indice"] = demand_score(enriched, all_items, as_of)
    enriched["prioridade"] = priority(float(enriched["indice"]))
    return enriched


def choose_next_increment(demand_pareto, automation_pareto):
    active_count = sum(
        1 for x in demand_pareto if x.get("status") in ACTIVE_STATUSES
    )
    allowed_statuses = ACTIVE_STATUSES if active_count >= WIP_LIMIT else ACTIONABLE_STATUSES
    candidates = [
        x for x in demand_pareto if x.get("status") in allowed_statuses
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda x: (-float(x["indice"]), str(x.get("id", "")))
    )
    top = candidates[0]
    return {
        "id": top["id"],
        "titulo": top["titulo"],
        "status": top["status"],
        "prioridade": top["prioridade"],
        "indice": top["indice"],
        "aging_dias": top["aging_dias"],
        "proxima_acao": top.get("proxima_acao", ""),
        "automacao_maior_retorno": (
            automation_pareto[0]["tarefa"] if automation_pareto else None
        ),
    }


def root_cause_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for item in items:
        root = str(item.get("causa_raiz_id", "")).strip()
        if root and item.get("status") in OPEN_STATUSES:
            groups[root].append(str(item["id"]))
    return [
        {"causa_raiz_id": root, "itens": sorted(ids), "quantidade": len(ids)}
        for root, ids in sorted(groups.items())
        if len(ids) > 1
    ]


def build_snapshot(demands, library, automations, as_of: date):
    errors = (
        validate_demands(demands)
        + validate_library(library)
        + validate_automations(automations)
    )
    if errors:
        raise ValueError("Falha de governanca:\n- " + "\n- ".join(errors))

    enriched = [enrich_demand(item, demands, as_of) for item in demands]
    dp = pareto(enriched, lambda item: float(item["indice"]))
    ap = pareto(automations, automation_score)
    open_demands = [x for x in enriched if x.get("status") in OPEN_STATUSES]
    blocked = [
        x for x in enriched if x.get("status") == "Bloqueada externamente"
    ]
    completed = [x for x in enriched if x.get("status") == "Concluido"]
    active = [x for x in enriched if x.get("status") in ACTIVE_STATUSES]
    blocker_counts = {
        kind: sum(1 for x in blocked if x.get("tipo_bloqueio") == kind)
        for kind in sorted(BLOCKER_TYPES - {"Nenhum"})
    }
    aging_counts = {
        level: sum(1 for x in open_demands if x["aging_nivel"] == level)
        for level in ("normal", "atencao", "escalar", "critico")
    }
    state_counts = Counter(str(x.get("status")) for x in enriched)
    mode = "semanal_aprofundado" if as_of.weekday() == 0 else "diario"

    snapshot = {
        "version": VERSION,
        "as_of": as_of.isoformat(),
        "mode": mode,
        "input_hashes": {
            "demandas_sha256": canonical_sha256(demands),
            "biblioteca_sha256": canonical_sha256(library),
            "automacoes_sha256": canonical_sha256(automations),
        },
        "governance": {
            "valid": True,
            "errors": [],
            "wip_limit": WIP_LIMIT,
            "wip_current": len(active),
            "wip_available": WIP_LIMIT - len(active),
        },
        "metrics": {
            "demandas_total": len(demands),
            "demandas_abertas": len(open_demands),
            "demandas_bloqueadas_externamente": len(blocked),
            "demandas_concluidas": len(completed),
            "demandas_ativas_wip": len(active),
            "componentes_reutilizaveis": len(library),
            "automacoes_candidatas": len(automations),
            "bloqueios_por_tipo": blocker_counts,
            "aging_por_nivel": aging_counts,
            "estados": dict(sorted(state_counts.items())),
        },
        "root_cause_groups": root_cause_groups(enriched),
        "next_increment": choose_next_increment(dp, ap),
    }
    report = {
        "version": VERSION,
        "as_of": as_of.isoformat(),
        "demandas": [
            {k: v for k, v in item.items() if k != "evidencia"} for item in dp
        ],
        "automacoes": ap,
    }
    return snapshot, report


def history_record(snapshot, report):
    top = report["demandas"][0] if report.get("demandas") else None
    open_ids = sorted(
        item["id"]
        for item in report.get("demandas", [])
        if item.get("status") in OPEN_STATUSES
    )
    return {
        "as_of": snapshot["as_of"],
        "version": snapshot["version"],
        "mode": snapshot["mode"],
        "input_hashes": snapshot["input_hashes"],
        "metrics": snapshot["metrics"],
        "next_increment": snapshot.get("next_increment"),
        "open_demand_ids": open_ids,
        "top_pareto": (
            None
            if top is None
            else {
                "id": top["id"],
                "titulo": top["titulo"],
                "indice": top["indice"],
                "prioridade": top["prioridade"],
            }
        ),
    }


def merge_history(previous, record, limit_days=HISTORY_LIMIT_DAYS):
    by_date = {
        str(x.get("as_of")): x
        for x in previous
        if str(x.get("as_of", "")).strip()
    }
    by_date[record["as_of"]] = record
    ordered = [by_date[k] for k in sorted(by_date)]
    return ordered[-limit_days:] if limit_days > 0 else ordered


def recurrence_summary(history, report):
    counts: Counter[str] = Counter()
    for item in history:
        for demand_id in item.get("open_demand_ids", []) or []:
            counts[str(demand_id)] += 1

    by_id = {str(item["id"]): item for item in report.get("demandas", [])}
    recurring = [
        {
            "id": demand_id,
            "ciclos": cycles,
            "status": by_id.get(demand_id, {}).get("status"),
        }
        for demand_id, cycles in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        if cycles >= RECURRENCE_AUTOMATION_CYCLES and demand_id in by_id
    ]
    automation_candidates = [
        item
        for item in recurring
        if item["status"] not in {"Bloqueada externamente", "Concluido", "Cancelado", "Duplicada"}
    ]
    return {
        "limiar_ciclos": RECURRENCE_AUTOMATION_CYCLES,
        "itens_recorrentes": recurring,
        "candidatos_automacao": automation_candidates,
    }


def apply_recurrence(snapshot, report, history):
    recurrence = recurrence_summary(history, report)
    snapshot["recurrence"] = recurrence
    report["recurrence"] = recurrence
    return recurrence


def history_summary(history):
    counts = {}
    for item in history:
        top = item.get("top_pareto")
        if isinstance(top, dict) and top.get("id"):
            counts[top["id"]] = counts.get(top["id"], 0) + 1
    recurring = (
        sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
        if counts
        else None
    )
    return {
        "dias": len(history),
        "bloqueios_total": sum(
            int(
                x.get("metrics", {}).get(
                    "demandas_bloqueadas_externamente",
                    x.get("metrics", {}).get("demandas_bloqueadas", 0),
                )
                or 0
            )
            for x in history
        ),
        "top_pareto_recorrente": recurring,
    }


def markdown(snapshot, report, history):
    m = snapshot["metrics"]
    hs = history_summary(history)
    recurrence = snapshot.get("recurrence") or recurrence_summary(history, report)
    gov = snapshot["governance"]

    lines = [
        "# Personal Process Control",
        "",
        f"Data de referencia: `{snapshot['as_of']}`",
        f"Modo: **{snapshot['mode']}**",
        "",
        "## Governanca",
        "",
        "- Status: VALIDADO",
        "- Itens invalidos: 0",
        f"- WIP: {gov['wip_current']}/{gov['wip_limit']}",
        f"- Capacidade WIP disponivel: {gov['wip_available']}",
        "",
        "## Indicadores",
        "",
        f"- Demandas totais: {m['demandas_total']}",
        f"- Demandas abertas: {m['demandas_abertas']}",
        f"- Demandas bloqueadas externamente: {m['demandas_bloqueadas_externamente']}",
        f"- Demandas concluidas: {m['demandas_concluidas']}",
        f"- Demandas ativas no WIP: {m['demandas_ativas_wip']}",
        f"- Aging critico: {m['aging_por_nivel']['critico']}",
        f"- Aging para escalar: {m['aging_por_nivel']['escalar']}",
        f"- Componentes reutilizaveis: {m['componentes_reutilizaveis']}",
        f"- Automacoes candidatas cadastradas: {m['automacoes_candidatas']}",
        f"- Dias de historico: {hs['dias']}",
        "",
        "## Fila governada",
        "",
        "| Ordem | ID | Status | Aging | Indice | Prioridade | Proxima acao |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for i, item in enumerate(report["demandas"], 1):
        next_action = str(item.get("proxima_acao", "")).replace("|", "/")
        lines.append(
            f"| {i} | {item['id']} | {item['status']} | {item['aging_dias']}d | "
            f"{item['indice']} | {item['prioridade']} | {next_action} |"
        )

    lines += ["", "## Proximo incremento executavel", ""]
    nxt = snapshot.get("next_increment")
    if nxt:
        lines += [
            f"- ID: `{nxt['id']}`",
            f"- Titulo: {nxt['titulo']}",
            f"- Status: {nxt['status']}",
            f"- Prioridade: {nxt['prioridade']}",
            f"- Aging: {nxt['aging_dias']} dias",
            f"- Proxima acao: {nxt['proxima_acao']}",
        ]
        if nxt.get("automacao_maior_retorno"):
            lines.append(
                f"- Automacao de maior retorno: {nxt['automacao_maior_retorno']}"
            )
    else:
        lines.append("- Nenhum item executavel; revisar bloqueios externos ou triagem.")

    if recurrence["candidatos_automacao"]:
        lines += ["", "## Gatilhos de automacao por recorrencia", ""]
        for item in recurrence["candidatos_automacao"]:
            lines.append(
                f"- `{item['id']}` permaneceu aberto por {item['ciclos']} ciclos; "
                "criar ou vincular incremento para eliminar a intervencao recorrente."
            )

    if snapshot["root_cause_groups"]:
        lines += ["", "## Causas raiz compartilhadas", ""]
        for group in snapshot["root_cause_groups"]:
            lines.append(
                f"- `{group['causa_raiz_id']}`: {', '.join(group['itens'])}"
            )

    if snapshot["mode"] == "semanal_aprofundado":
        lines += [
            "",
            "## Revisao semanal aprofundada",
            "",
            f"- Dias consolidados no historico: {hs['dias']}",
            f"- Soma de ocorrencias de bloqueio externo no periodo: {hs['bloqueios_total']}",
            f"- Top Pareto mais recorrente: {hs['top_pareto_recorrente'] or 'N/D'}",
            "- Revisar bloqueios recorrentes por causa raiz.",
            "- Revisar tarefas manuais de maior indice de automacao.",
            "- Promover solucoes recorrentes para a biblioteca reutilizavel.",
            f"- Respeitar WIP maximo de {WIP_LIMIT} itens ativos.",
        ]
    return "\n".join(lines) + "\n"


def col_letter(index):
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def sheet_xml(rows):
    body = []
    for r_idx, row in enumerate(rows, 1):
        cells = []
        for c_idx, value in enumerate(row, 1):
            ref = f"{col_letter(c_idx)}{r_idx}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>'
                    f'{escape("" if value is None else str(value))}'
                    f"</t></is></c>"
                )
        body.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(body)
        + "</sheetData></worksheet>"
    )


def write_zip_text(zf, name, content):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    zf.writestr(info, content.encode())


def write_xlsx(path, snapshot, demands, library, automations, history):
    report_demands = [
        enrich_demand(item, demands, date.fromisoformat(snapshot["as_of"]))
        for item in demands
    ]
    sheets = [
        (
            "Dashboard",
            [
                ["Indicador", "Valor"],
                ["Data", snapshot["as_of"]],
                ["Modo", snapshot["mode"]],
                ["Dias historico", len(history)],
                ["WIP atual", snapshot["governance"]["wip_current"]],
                ["WIP limite", snapshot["governance"]["wip_limit"]],
                ["Aging critico", snapshot["metrics"]["aging_por_nivel"]["critico"]],
            ],
        ),
        (
            "Demandas",
            [
                [
                    "ID",
                    "Titulo",
                    "Area",
                    "Status",
                    "Impacto",
                    "Esforco",
                    "Frequencia",
                    "Aging dias",
                    "Aging nivel",
                    "Fator desbloqueio",
                    "Fator urgencia",
                    "Proxima acao",
                    "Tipo bloqueio",
                    "Responsavel bloqueio",
                    "Dependencias",
                    "Causa raiz",
                    "Origem",
                    "Evidenciado em",
                    "Ultima movimentacao",
                    "Evidencia",
                ]
            ]
            + [
                [
                    x.get("id"),
                    x.get("titulo"),
                    x.get("area"),
                    x.get("status"),
                    x.get("impacto"),
                    x.get("esforco"),
                    x.get("frequencia"),
                    x.get("aging_dias"),
                    x.get("aging_nivel"),
                    x.get("fator_desbloqueio"),
                    x.get("fator_urgencia"),
                    x.get("proxima_acao"),
                    x.get("tipo_bloqueio"),
                    x.get("responsavel_bloqueio"),
                    ",".join(x.get("dependencias", [])),
                    x.get("causa_raiz_id"),
                    x.get("origem"),
                    x.get("estado_evidenciado_em"),
                    x.get("ultima_movimentacao_em"),
                    x.get("evidencia"),
                ]
                for x in report_demands
            ],
        ),
        (
            "Biblioteca",
            [["ID", "Nome", "Tipo", "Area", "Versao", "Status"]]
            + [
                [
                    x.get("id"),
                    x.get("nome"),
                    x.get("tipo"),
                    x.get("area"),
                    x.get("versao"),
                    x.get("status"),
                ]
                for x in library
            ],
        ),
        (
            "Automacoes",
            [
                [
                    "ID",
                    "Tarefa",
                    "Area",
                    "Frequencia",
                    "Tempo manual min",
                    "Impacto",
                    "Esforco",
                    "Status",
                    "Proxima acao",
                ]
            ]
            + [
                [
                    x.get("id"),
                    x.get("tarefa"),
                    x.get("area"),
                    x.get("frequencia"),
                    x.get("tempo_manual_min"),
                    x.get("impacto"),
                    x.get("esforco_automacao"),
                    x.get("status"),
                    x.get("proxima_acao"),
                ]
                for x in automations
            ],
        ),
        (
            "Historico",
            [
                [
                    "Data",
                    "Modo",
                    "Demandas abertas",
                    "Bloqueadas externas",
                    "Concluidas",
                    "WIP",
                    "Top Pareto",
                    "Indice",
                ]
            ]
            + [
                [
                    h.get("as_of"),
                    h.get("mode"),
                    h.get("metrics", {}).get("demandas_abertas"),
                    h.get("metrics", {}).get(
                        "demandas_bloqueadas_externamente",
                        h.get("metrics", {}).get("demandas_bloqueadas"),
                    ),
                    h.get("metrics", {}).get("demandas_concluidas"),
                    h.get("metrics", {}).get("demandas_ativas_wip"),
                    (h.get("top_pareto") or {}).get("id"),
                    (h.get("top_pareto") or {}).get("indice"),
                ]
                for h in history
            ],
        ),
    ]
    ct = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    ] + [
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    ] + ["</Types>"]
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (name, _) in enumerate(sheets, 1)
        )
        + "</sheets></workbook>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Relationships>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        write_zip_text(zf, "[Content_Types].xml", "".join(ct))
        write_zip_text(zf, "_rels/.rels", rels)
        write_zip_text(zf, "xl/workbook.xml", workbook)
        write_zip_text(zf, "xl/_rels/workbook.xml.rels", wb_rels)
        for i, (_, rows) in enumerate(sheets, 1):
            write_zip_text(
                zf,
                f"xl/worksheets/sheet{i}.xml",
                sheet_xml(rows),
            )


def parse_as_of(raw):
    if raw and raw.strip():
        try:
            return date.fromisoformat(raw.strip())
        except ValueError as exc:
            raise ValueError("--as-of deve usar YYYY-MM-DD") from exc
    return datetime.now(timezone.utc).date()


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--input-dir",
        type=Path,
        default=Path("governance/personal-process"),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/personal-process"),
    )
    p.add_argument("--history-input", type=Path, default=None)
    p.add_argument("--as-of", default="")
    a = p.parse_args()

    demands = load_json(a.input_dir / "demandas.json")
    library = load_json(a.input_dir / "biblioteca.json")
    automations = load_json(a.input_dir / "automacoes.json")
    previous = load_optional_history(a.history_input)
    if not all(isinstance(x, list) for x in (demands, library, automations)):
        raise ValueError("Entradas devem ser arrays JSON")

    snapshot, report = build_snapshot(
        demands,
        library,
        automations,
        parse_as_of(a.as_of),
    )
    history = merge_history(previous, history_record(snapshot, report))
    apply_recurrence(snapshot, report, history)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (a.out_dir / "pareto.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (a.out_dir / "historico.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (a.out_dir / "relatorio.md").write_text(
        markdown(snapshot, report, history),
        encoding="utf-8",
    )
    write_xlsx(
        a.out_dir / "controle_mestre_processos.xlsx",
        snapshot,
        demands,
        library,
        automations,
        history,
    )
    print(markdown(snapshot, report, history))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
