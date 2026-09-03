#!/usr/bin/env python3
"""Personal Process Control v1.

Controle de processos independente do domínio funcional do ReqSys.
Usa somente a biblioteca padrão do Python, valida governança, calcula Pareto,
seleciona próximo incremento e gera JSON, Markdown e XLSX autocontido.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

OPEN_STATUSES = {"Backlog", "Proxima acao", "Em execucao", "Bloqueado"}
ALL_STATUSES = OPEN_STATUSES | {"Concluido", "Cancelado"}
BLOCKER_TYPES = {"Nenhum", "Humano", "Tecnico", "Externo"}


def load_json(path: Path) -> Any:
    if not path.exists():
        raise ValueError(f"Arquivo obrigatorio ausente: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido em {path}: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require_text(item: dict[str, Any], field: str, context: str, errors: list[str]) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}: campo '{field}' obrigatorio")
        return ""
    return value.strip()


def require_score(item: dict[str, Any], field: str, context: str, errors: list[str], minimum: int = 1, maximum: int = 5) -> float:
    value = item.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < minimum or value > maximum:
        errors.append(f"{context}: campo '{field}' deve estar entre {minimum} e {maximum}")
        return 0.0
    return float(value)


def validate_unique_ids(items: list[dict[str, Any]], collection: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            errors.append(f"{collection}[{index}]: campo 'id' obrigatorio")
        elif item_id in seen:
            errors.append(f"{collection}: id duplicado '{item_id}'")
        else:
            seen.add(item_id)


def validate_demands(items: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list):
        return ["demandas: esperado array JSON"]
    dict_items = [x for x in items if isinstance(x, dict)]
    if len(dict_items) != len(items):
        errors.append("demandas: todos os itens devem ser objetos")
    validate_unique_ids(dict_items, "demandas", errors)
    for item in dict_items:
        ctx = f"demanda {item.get('id', '?')}"
        for field in ("titulo", "area", "problema"):
            require_text(item, field, ctx, errors)
        impact = require_score(item, "impacto", ctx, errors)
        effort = require_score(item, "esforco", ctx, errors)
        frequency = require_score(item, "frequencia", ctx, errors)
        if effort == 0 and (impact or frequency):
            errors.append(f"{ctx}: esforco nao pode ser zero")
        status = require_text(item, "status", ctx, errors)
        if status and status not in ALL_STATUSES:
            errors.append(f"{ctx}: status invalido '{status}'")
        blocker = str(item.get("tipo_bloqueio", "Nenhum")).strip() or "Nenhum"
        if blocker not in BLOCKER_TYPES:
            errors.append(f"{ctx}: tipo_bloqueio invalido '{blocker}'")
        if status in OPEN_STATUSES and not str(item.get("proxima_acao", "")).strip():
            errors.append(f"{ctx}: item aberto sem proxima_acao")
        if status == "Concluido":
            if not str(item.get("criterio_conclusao", "")).strip():
                errors.append(f"{ctx}: concluido sem criterio_conclusao")
            if not str(item.get("evidencia", "")).strip():
                errors.append(f"{ctx}: concluido sem evidencia")
        if status == "Bloqueado" and blocker == "Nenhum":
            errors.append(f"{ctx}: bloqueado sem tipo_bloqueio")
    return errors


def validate_library(items: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list):
        return ["biblioteca: esperado array JSON"]
    dict_items = [x for x in items if isinstance(x, dict)]
    if len(dict_items) != len(items):
        errors.append("biblioteca: todos os itens devem ser objetos")
    validate_unique_ids(dict_items, "biblioteca", errors)
    for item in dict_items:
        ctx = f"componente {item.get('id', '?')}"
        for field in ("nome", "tipo", "area", "problema_resolvido", "versao", "status"):
            require_text(item, field, ctx, errors)
    return errors


def validate_automations(items: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list):
        return ["automacoes: esperado array JSON"]
    dict_items = [x for x in items if isinstance(x, dict)]
    if len(dict_items) != len(items):
        errors.append("automacoes: todos os itens devem ser objetos")
    validate_unique_ids(dict_items, "automacoes", errors)
    for item in dict_items:
        ctx = f"automacao {item.get('id', '?')}"
        for field in ("tarefa", "area", "status", "proxima_acao"):
            require_text(item, field, ctx, errors)
        require_score(item, "frequencia", ctx, errors)
        require_score(item, "impacto", ctx, errors)
        effort = require_score(item, "esforco_automacao", ctx, errors)
        minutes = item.get("tempo_manual_min")
        if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes < 0:
            errors.append(f"{ctx}: tempo_manual_min deve ser >= 0")
        if effort == 0:
            errors.append(f"{ctx}: esforco_automacao nao pode ser zero")
    return errors


def demand_score(item: dict[str, Any]) -> float:
    return round((float(item["impacto"]) * float(item["frequencia"])) / float(item["esforco"]), 4)


def automation_score(item: dict[str, Any]) -> float:
    return round((float(item["frequencia"]) * float(item["tempo_manual_min"]) * float(item["impacto"])) / float(item["esforco_automacao"]), 4)


def priority(score: float) -> str:
    if score >= 15:
        return "P0 - Critica"
    if score >= 8:
        return "P1 - Alta"
    if score >= 4:
        return "P2 - Media"
    return "P3 - Baixa"


def pareto(items: list[dict[str, Any]], score_fn) -> list[dict[str, Any]]:
    scored = [{**item, "indice": score_fn(item)} for item in items]
    scored.sort(key=lambda x: (-x["indice"], str(x.get("id", ""))))
    total = sum(x["indice"] for x in scored)
    cumulative = 0.0
    result: list[dict[str, Any]] = []
    reached = False
    for item in scored:
        cumulative += item["indice"]
        pct = 0.0 if total <= 0 else round(cumulative / total * 100, 2)
        critical = not reached
        result.append({**item, "percentual_acumulado": pct, "faixa_pareto": "prioritario" if critical else "cauda"})
        if pct >= 80:
            reached = True
    return result


def choose_next_increment(demand_pareto: list[dict[str, Any]], automation_pareto: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [x for x in demand_pareto if x.get("status") not in {"Concluido", "Cancelado"}]
    if not candidates:
        return None
    top = candidates[0]
    return {
        "id": top["id"],
        "titulo": top["titulo"],
        "prioridade": priority(float(top["indice"])),
        "indice": top["indice"],
        "proxima_acao": top.get("proxima_acao", ""),
        "automacao_maior_retorno": automation_pareto[0]["tarefa"] if automation_pareto else None,
    }


def build_snapshot(demands: list[dict[str, Any]], library: list[dict[str, Any]], automations: list[dict[str, Any]], as_of: date) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = validate_demands(demands) + validate_library(library) + validate_automations(automations)
    if errors:
        raise ValueError("Falha de governanca:\n- " + "\n- ".join(errors))
    demand_pareto = pareto(demands, demand_score)
    automation_pareto = pareto(automations, automation_score)
    open_demands = [x for x in demands if x.get("status") in OPEN_STATUSES]
    blocked = [x for x in demands if x.get("status") == "Bloqueado"]
    completed = [x for x in demands if x.get("status") == "Concluido"]
    blocker_counts = {kind: sum(1 for x in blocked if x.get("tipo_bloqueio") == kind) for kind in sorted(BLOCKER_TYPES - {"Nenhum"})}
    next_increment = choose_next_increment(demand_pareto, automation_pareto)
    mode = "semanal_aprofundado" if as_of.weekday() == 0 else "diario"
    snapshot = {
        "version": "1.0.0",
        "as_of": as_of.isoformat(),
        "mode": mode,
        "input_hashes": {
            "demandas_sha256": canonical_sha256(demands),
            "biblioteca_sha256": canonical_sha256(library),
            "automacoes_sha256": canonical_sha256(automations),
        },
        "governance": {"valid": True, "errors": []},
        "metrics": {
            "demandas_total": len(demands),
            "demandas_abertas": len(open_demands),
            "demandas_bloqueadas": len(blocked),
            "demandas_concluidas": len(completed),
            "componentes_reutilizaveis": len(library),
            "automacoes_candidatas": len(automations),
            "bloqueios_por_tipo": blocker_counts,
        },
        "next_increment": next_increment,
    }
    pareto_report = {
        "version": "1.0.0",
        "as_of": as_of.isoformat(),
        "demandas": [{k: v for k, v in item.items() if k not in {"evidencia"}} | {"prioridade": priority(float(item["indice"]))} for item in demand_pareto],
        "automacoes": automation_pareto,
    }
    return snapshot, pareto_report


def markdown(snapshot: dict[str, Any], pareto_report: dict[str, Any]) -> str:
    m = snapshot["metrics"]
    lines = ["# Personal Process Control", "", f"Data de referencia: `{snapshot['as_of']}`", f"Modo: **{snapshot['mode']}**", "", "## Governanca", "", "- Status: VALIDADO", "- Itens invalidos: 0", "", "## Indicadores", "", f"- Demandas totais: {m['demandas_total']}", f"- Demandas abertas: {m['demandas_abertas']}", f"- Demandas bloqueadas: {m['demandas_bloqueadas']}", f"- Demandas concluidas: {m['demandas_concluidas']}", f"- Componentes reutilizaveis: {m['componentes_reutilizaveis']}", f"- Automacoes candidatas: {m['automacoes_candidatas']}", "", "## Pareto de demandas", "", "| Ordem | ID | Titulo | Indice | Prioridade | Faixa |", "|---:|---|---|---:|---|---|"]
    for idx, item in enumerate(pareto_report["demandas"], start=1):
        lines.append(f"| {idx} | {item['id']} | {item['titulo']} | {item['indice']} | {item['prioridade']} | {item['faixa_pareto']} |")
    lines.extend(["", "## Proximo incremento", ""])
    nxt = snapshot.get("next_increment")
    if nxt:
        lines.extend([f"- ID: `{nxt['id']}`", f"- Titulo: {nxt['titulo']}", f"- Prioridade: {nxt['prioridade']}", f"- Proxima acao: {nxt['proxima_acao']}"])
        if nxt.get("automacao_maior_retorno"):
            lines.append(f"- Automacao de maior retorno: {nxt['automacao_maior_retorno']}")
    else:
        lines.append("- Nenhuma demanda aberta.")
    if snapshot["mode"] == "semanal_aprofundado":
        lines.extend(["", "## Revisao semanal aprofundada", "", "- Revisar bloqueios recorrentes por causa raiz.", "- Revisar tarefas manuais de maior indice de automacao.", "- Promover solucoes recorrentes para a biblioteca reutilizavel.", "- Manter no maximo tres focos ativos de maior retorno."])
    lines.append("")
    return "\n".join(lines)


def col_letter(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def sheet_xml(rows: list[list[Any]]) -> str:
    body: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            ref = f"{col_letter(c_idx)}{r_idx}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                text = "" if value is None else escape(str(value))
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        body.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(body) + '</sheetData></worksheet>'


def write_zip_text(zf: zipfile.ZipFile, name: str, content: str) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    zf.writestr(info, content.encode("utf-8"))


def write_xlsx(path: Path, snapshot: dict[str, Any], demands: list[dict[str, Any]], library: list[dict[str, Any]], automations: list[dict[str, Any]]) -> None:
    sheets = [
        ("Dashboard", [["Indicador", "Valor"], ["Data", snapshot["as_of"]], ["Modo", snapshot["mode"]]] + [[k, v if not isinstance(v, dict) else json.dumps(v, ensure_ascii=False)] for k, v in snapshot["metrics"].items()]),
        ("Demandas", [["ID", "Titulo", "Area", "Status", "Impacto", "Esforco", "Frequencia", "Proxima acao", "Tipo bloqueio", "Evidencia"]] + [[x.get("id"), x.get("titulo"), x.get("area"), x.get("status"), x.get("impacto"), x.get("esforco"), x.get("frequencia"), x.get("proxima_acao"), x.get("tipo_bloqueio"), x.get("evidencia")] for x in demands]),
        ("Biblioteca", [["ID", "Nome", "Tipo", "Area", "Versao", "Status"]] + [[x.get("id"), x.get("nome"), x.get("tipo"), x.get("area"), x.get("versao"), x.get("status")] for x in library]),
        ("Automacoes", [["ID", "Tarefa", "Area", "Frequencia", "Tempo manual min", "Impacto", "Esforco", "Status", "Proxima acao"]] + [[x.get("id"), x.get("tarefa"), x.get("area"), x.get("frequencia"), x.get("tempo_manual_min"), x.get("impacto"), x.get("esforco_automacao"), x.get("status"), x.get("proxima_acao")] for x in automations]),
    ]
    content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    for idx in range(1, len(sheets) + 1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append('</Types>')
    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + ''.join(f'<sheet name="{escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>' for idx, (name, _) in enumerate(sheets, start=1)) + '</sheets></workbook>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    wb_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>' for idx in range(1, len(sheets)+1)) + '</Relationships>'
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        write_zip_text(zf, "[Content_Types].xml", "".join(content_types))
        write_zip_text(zf, "_rels/.rels", rels)
        write_zip_text(zf, "xl/workbook.xml", workbook)
        write_zip_text(zf, "xl/_rels/workbook.xml.rels", wb_rels)
        for idx, (_, rows) in enumerate(sheets, start=1):
            write_zip_text(zf, f"xl/worksheets/sheet{idx}.xml", sheet_xml(rows))


def parse_as_of(raw: str | None) -> date:
    if raw and raw.strip():
        try:
            return date.fromisoformat(raw.strip())
        except ValueError as exc:
            raise ValueError("--as-of deve usar YYYY-MM-DD") from exc
    return datetime.now(timezone.utc).date()


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa o Personal Process Control v1")
    parser.add_argument("--input-dir", type=Path, default=Path("governance/personal-process"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/personal-process"))
    parser.add_argument("--as-of", default="")
    args = parser.parse_args()
    demands = load_json(args.input_dir / "demandas.json")
    library = load_json(args.input_dir / "biblioteca.json")
    automations = load_json(args.input_dir / "automacoes.json")
    if not all(isinstance(x, list) for x in (demands, library, automations)):
        raise ValueError("Entradas devem ser arrays JSON")
    as_of = parse_as_of(args.as_of)
    snapshot, pareto_report = build_snapshot(demands, library, automations, as_of)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "pareto.json").write_text(json.dumps(pareto_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "relatorio.md").write_text(markdown(snapshot, pareto_report), encoding="utf-8")
    write_xlsx(args.out_dir / "controle_mestre_processos.xlsx", snapshot, demands, library, automations)
    print(markdown(snapshot, pareto_report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
