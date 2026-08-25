import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "governance/tooling/ops-dashboard-consolidation-phase1.json"
INVENTORY_PATH = ROOT / "governance/tooling/rationalization-inventory.json"
GENERATOR_PATH = ROOT / "tools/geradores/movimento_email_autocontido.py"

TEAMS_CONSUMERS = [
    ".github/workflows/teams-notification-dashboard.yml",
    ".github/workflows/teams-public-dashboard-smoke.yml",
    ".github/workflows/teams-certification-dashboard-contract.yml",
    ".github/workflows/teams-public-dashboard-smoke-contract.yml",
    ".github/workflows/teams-service-operational-readiness.yml",
    ".github/workflows/deploy-reqsys-pages-composite.yml",
    ".github/workflows/teams-gold-certification.yml",
]

LEGACY_TEAMS_RE = re.compile(r"(?<!docs/)ops-dashboard/teams-notification")
LEGACY_MOVIMENTO_DEFAULT_RE = re.compile(
    r"(?<!docs/)ops-dashboard/movimento-email/data\.json"
)


def test_canonical_dashboard_assets_exist() -> None:
    assert (ROOT / "docs/ops-dashboard/teams-notification/index.html").is_file()
    assert (ROOT / "docs/ops-dashboard/movimento-email/index.html").is_file()


def test_teams_operational_consumers_use_canonical_path() -> None:
    for relative_path in TEAMS_CONSUMERS:
        path = ROOT / relative_path
        assert path.is_file(), f"Consumidor operacional ausente: {relative_path}"
        content = path.read_text(encoding="utf-8")
        assert not LEGACY_TEAMS_RE.search(content), (
            f"Referência Teams legada encontrada em {relative_path}"
        )


def test_legacy_root_cannot_be_removed_while_generator_default_is_legacy() -> None:
    generator = GENERATOR_PATH.read_text(encoding="utf-8")
    still_legacy = bool(LEGACY_MOVIMENTO_DEFAULT_RE.search(generator))
    legacy_root_exists = (ROOT / "ops-dashboard").is_dir()

    assert not (still_legacy and not legacy_root_exists), (
        "ops-dashboard/ foi removido enquanto o gerador Movimento Email ainda "
        "usa o destino padrão legado."
    )


def test_phase_evidence_declares_remaining_blocker() -> None:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert evidence["canonical_target"] == "docs/ops-dashboard"
    assert evidence["legacy_root_removed"] is False
    assert evidence["removal_authorized"] is False
    blockers = evidence["remaining_blockers"]
    assert any(item["path"] == "tools/geradores/movimento_email_autocontido.py" for item in blockers)


def test_inventory_keeps_legacy_dashboard_in_consolidation_until_blocker_is_zero() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    item = next(entry for entry in inventory["decisions"] if entry["id"] == "ops-dashboard")
    assert item["decision"] == "CONSOLIDAR"
    assert item["target"] == "docs/ops-dashboard"
    assert item["blocking_dependencies"]
