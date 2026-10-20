#!/usr/bin/env python3
"""Check recovered baseline API prerequisites, never certify unexecuted tests.

Run with an isolated Python from a clean venv containing only the verified wheel.
This is an import-contract probe: historical test bodies are NOT executed here.
Exit 2 means the complete baseline remains uncertified, including when imports pass.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import socket
import sys

CONSUMER_SHA = "f487837fa553a0f5f8af753963539e60a79dbe19"
ENGINE_SHA = "15dd067032d7c55e22186ef3587c0d694d0392fd"
WHEEL_SHA256 = "9301bc1ec426cb2a223b6beca6802c97f576bd5a89c4cf73a1b1f0a15d08b7ea"
INVENTORY_BLOB = "51dbc603e7421bf7117059b5e1ae94cbb0142c1b"
IDS_SHA256 = "5ccf93074b4dafe3964e8c5ab0654ba516a65e1827db1ff5cc4c2fa09c27ec93"
GROUP_COUNTS = {
    "tests/test_casos_uso.py": 18,
    "tests/test_metrica.py": 21,
    "tests/test_privacidade.py": 24,
    "tests/test_verificacao.py": 29,
}
CONTRACTS = {
    "ocr_evidencia.adaptadores.repositorio_jsonl": {"RelogioFixo", "RepositorioJsonl", "RepositorioMemoria"},
    "ocr_evidencia.aplicacao.casos_uso": {"ConsolidarEvidencia", "PoliticaDecisao", "RegistrarObservacao"},
    "ocr_evidencia.dominio.medicao": {"EstadoDecisao", "Observacao", "ResultadoComparacao"},
    "ocr_evidencia.dominio.metrica": {"ConfiguracaoGate", "amostras_necessarias", "avaliar_gate", "consolidar", "erro_calibracao_esperado", "limite_inferior_wilson"},
    "ocr_evidencia.portas.protocolos": {"Relogio", "RepositorioObservacoes"},
    "ocr_evidencia.dominio.divergencia": {"ClasseDivergencia", "ModoComparacao", "classificar_divergencia", "modo_para_campo", "normalizar"},
    "ocr_evidencia.dominio.mascaramento": {"ErroPIIDetectada", "mascarar_cnpj", "mascarar_cpf", "mascarar_generico", "validar_ausencia_de_pii"},
    "ocr_evidencia.dominio.verificacao": {"Forca", "Situacao", "verificar_campo", "verificar_cep", "verificar_cnh", "verificar_cnpj", "verificar_cpf", "verificar_data_nascimento", "verificar_pis", "_FAIXAS_CEP"},
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def ids_for(group: dict) -> list[str]:
    return [group["path"] + "::" + cls + "::" + method
            for cls, methods in group["cases"].items() for method in methods]


def validate_inventory(data: dict) -> list[str]:
    require(data.get("schema_version") == "1.0.0", "inventory_schema_mismatch")
    require(data.get("expected_cases") == 92, "baseline_count_changed")
    require(data.get("consumer_sha") == CONSUMER_SHA, "consumer_sha_mismatch")
    require(data.get("engine_sha") == ENGINE_SHA, "engine_sha_mismatch")
    require(data.get("wheel_sha256") == WHEEL_SHA256, "wheel_digest_mismatch")
    require(data.get("baseline_functional_certified") is False, "false_baseline_certification")
    groups = data.get("groups", [])
    require(len(groups) == 4, "baseline_group_count_changed")
    require({g["path"] for g in groups} == set(GROUP_COUNTS), "baseline_file_set_changed")
    observed_contracts: dict[str, set[str]] = {}
    all_ids: list[str] = []
    for group in groups:
        group_ids = ids_for(group)
        require(len(group_ids) == GROUP_COUNTS[group["path"]] == group.get("expected_cases"), "baseline_group_case_count_changed")
        require(bool(group.get("contracts")), "baseline_contracts_missing")
        require(bool(re.fullmatch(r"[a-f0-9]{64}", group.get("sha256", ""))), "legacy_file_digest_invalid")
        for module, symbols in group["contracts"].items():
            require(module in CONTRACTS and bool(symbols), "unexpected_module_contract")
            require(len(symbols) == len(set(symbols)), "duplicate_contract_symbol")
            observed_contracts.setdefault(module, set()).update(symbols)
        all_ids.extend(group_ids)
    all_ids.sort()
    require(len(all_ids) == len(set(all_ids)) == 92, "baseline_ids_missing_or_duplicate")
    digest = hashlib.sha256(json.dumps(all_ids, separators=(",", ":")).encode()).hexdigest()
    require(digest == IDS_SHA256, "baseline_ids_changed")
    require(observed_contracts == CONTRACTS, "baseline_import_contracts_changed")
    return all_ids


def load_inventory(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    require(blob == INVENTORY_BLOB, "inventory_bytes_changed")
    data = json.loads(raw)
    validate_inventory(data)
    return data, hashlib.sha256(raw).hexdigest()


def self_test(data: dict) -> dict:
    validate_inventory(data)
    mutations = []
    for label in ("missing_case", "duplicate_case", "replaced_case", "missing_contracts", "wrong_sha", "false_certification", "missing_symbol"):
        item = copy.deepcopy(data)
        methods = item["groups"][0]["cases"]["TestRegistrarObservacao"]
        if label == "missing_case":
            methods.pop()
        elif label == "duplicate_case":
            methods[-1] = methods[0]
        elif label == "replaced_case":
            methods[-1] = "test_fake_replacement_same_count"
        elif label == "missing_contracts":
            item["groups"][0]["contracts"] = {}
        elif label == "wrong_sha":
            item["engine_sha"] = "0" * 40
        elif label == "false_certification":
            item["baseline_functional_certified"] = True
        else:
            item["groups"][3]["contracts"]["ocr_evidencia.dominio.verificacao"].remove("verificar_cpf")
        try:
            validate_inventory(item)
        except ValueError:
            mutations.append(label)
        else:
            raise ValueError("self_test_false_positive:" + label)
    require(validate_inventory(data) == validate_inventory(copy.deepcopy(data)), "inventory_replay_mismatch")
    return {"valid_inventory_passed": True, "negative_controls_passed": mutations,
            "positive_revalidation_passed": True, "inventory_replay_identical": True,
            "historical_test_bodies_executed": 0}


def inspect_module(name: str, symbols: set[str]) -> dict:
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as error:
        missing = str(error.name or "")
        status = "MODULE_ABSENT" if missing == name or name.startswith(missing + ".") else "DEPENDENCY_IMPORT_FAILURE"
        return {"status": status, "missing_module": missing, "required_symbols": sorted(symbols)}
    except Exception as error:
        return {"status": "IMPORT_ERROR", "exception_type": type(error).__name__, "required_symbols": sorted(symbols)}
    origin = Path(module.__file__).resolve()
    require(origin.is_relative_to(Path(sys.prefix).resolve()) and "site-packages" in origin.parts,
            "import_not_from_isolated_installation:" + name)
    missing_symbols = sorted(symbol for symbol in symbols if not hasattr(module, symbol))
    return {"status": "SYMBOLS_ABSENT" if missing_symbols else "PRESENT",
            "origin": str(origin), "source_sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
            "required_symbols": sorted(symbols), "missing_symbols": missing_symbols}


def probe(data: dict, inventory_sha256: str) -> dict:
    require(sys.flags.isolated == 1 and sys.flags.no_user_site == 1, "isolated_python_required")
    require(sys.prefix != sys.base_prefix, "clean_venv_required")
    blocked_events = {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.bind", "subprocess.Popen", "os.system"}

    def deny_network(event: str, args: tuple) -> None:
        if event in blocked_events:
            raise RuntimeError("probe_network_or_process_denied")

    sys.addaudithook(deny_network)
    try:
        socket.getaddrinfo("localhost", 0)
    except RuntimeError as error:
        require(str(error) == "probe_network_or_process_denied", "network_control_wrong_error")
    else:
        raise ValueError("network_control_failed")
    positive = {name: inspect_module(name, set()) for name in (
        "ocr_evidencia", "ocr_evidencia.dominio.nome", "ocr_evidencia.adaptadores.ocr_tesseract")}
    require(all(item["status"] == "PRESENT" for item in positive.values()), "installed_core_positive_control_failed")
    require(importlib.metadata.version("ocr-evidence-engine") == "1.2.0", "installed_distribution_version_mismatch")
    require(importlib.import_module("ocr_evidencia").__version__ == "1.2.0", "installed_module_version_mismatch")
    negative = inspect_module("ocr_evidencia.__baseline92_missing_control__", set())
    require(negative["status"] == "MODULE_ABSENT", "missing_module_negative_control_failed")
    modules = {name: inspect_module(name, symbols) for name, symbols in sorted(CONTRACTS.items())}
    rows = []
    for group in data["groups"]:
        blockers = sorted(name for name in group["contracts"] if modules[name]["status"] != "PRESENT")
        for test_id in ids_for(group):
            rows.append({"test_id": test_id, "legacy_file_sha256": group["sha256"],
                         "api_prerequisites_available": not blockers,
                         "blocked_modules": blockers, "test_body_executed": False,
                         "functional_result": "NOT_EXECUTED", "semantic_equivalence": "NOT_PROVEN"})
    rows.sort(key=lambda row: row["test_id"])
    blocked = sum(bool(row["blocked_modules"]) for row in rows)
    require(len(rows) == 92, "matrix_incomplete")
    return {
        "schema_version": "1.0.0", "correlation_id": "ocr-baseline92-compat-20261020-f487837f",
        "audit_sha": os.environ.get("GITHUB_SHA", ""), "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "consumer_sha": CONSUMER_SHA, "engine_sha": ENGINE_SHA,
        "wheel_sha256": WHEEL_SHA256, "inventory_sha256": inventory_sha256,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version.split()[0], "python_isolated": True,
        "network_control": "PYTHON_AUDIT_HOOK_DENIED_DNS_NOT_OS_AIRGAP",
        "positive_controls": positive, "negative_control": negative,
        "modules": modules, "cases": rows,
        "cases_total": 92, "cases_import_ready": 92 - blocked, "cases_blocked": blocked,
        "historical_test_bodies_executed": 0, "baseline_functional_certified": False,
        "status": "BLOCKED_API_COMPATIBILITY" if blocked else "API_PRESENT_BASELINE_EXECUTION_REQUIRED",
        "production_touched": False, "pin_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    data, digest = load_inventory(args.inventory)
    result = self_test(data) if args.self_test else probe(data, digest)
    # Exclusive creation avoids silently replacing a previous audit's evidence.
    with args.output.open("xb") as stream:
        stream.write(canonical(result))
    print(json.dumps({"mode": "self-test" if args.self_test else "probe",
                      "status": result.get("status", "SELF_TEST_PASSED"),
                      "cases_blocked": result.get("cases_blocked"),
                      "historical_test_bodies_executed": 0}, sort_keys=True))
    # Import readiness alone must never produce a baseline certification.
    return 0 if args.self_test else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("BASELINE92_AUDIT_ERROR:" + type(error).__name__ + ":" + str(error)[:200], file=sys.stderr)
        raise SystemExit(3)
