from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "services/codex-worker-pool/app/main.py").read_text(encoding="utf-8")
COMPOSE = (ROOT / "docker-compose.pc24x7-codex-worker-pool.yml").read_text(encoding="utf-8")
README = (ROOT / "services/codex-worker-pool/README.md").read_text(encoding="utf-8")
RUNBOOK = (ROOT / "docs/runbooks/codex-worker-pool.md").read_text(encoding="utf-8")
REQUIREMENTS = (ROOT / ".sdd/specs/codex-worker-pool.requirements.md").read_text(encoding="utf-8")


def test_worker_pool_watchdog_defaults_to_canonical_300_seconds() -> None:
    assert 'CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS", "300"' in MAIN
    assert 'CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS: "300"' in COMPOSE
    assert 'CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS="300"' in README
    assert "CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS=300" in README
    assert "Após 300s sem avanço" in RUNBOOK
    assert "timeout padrão de ausência de progresso material deve ser 300 segundos" in REQUIREMENTS


def test_legacy_900_second_watchdog_default_is_not_reintroduced() -> None:
    assert 'CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS", "900"' not in MAIN
    assert 'CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS: "900"' not in COMPOSE
    assert 'CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS="900"' not in README
    assert "CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS=900" not in README
    assert "Após 900s sem avanço" not in RUNBOOK
