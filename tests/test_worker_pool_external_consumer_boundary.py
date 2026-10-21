from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEDICATED_WORKER_POOL_SHA = "5d8de580fea571404607aa80c7bd7637b4652db6"
CONSUMER_FILES = (
    ".github/workflows/codex-worker-pool-handoff.yml",
    "scripts/pending_development_worker_pool_bridge.py",
    "scripts/worker_pool_portable_contract_e2e.py",
    "scripts/hosted_worker_pool_reqsys_proof.py",
    "scripts/hosted_worker_pool_reqsys_task.py",
)
LEGACY_REFERENCES = (
    "services/codex-worker-pool",
    "docker-compose.pc24x7-codex-worker-pool.yml",
)


def normalized_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").replace("\\", "/")


def test_active_worker_pool_consumers_do_not_depend_on_reqsys_legacy_copy():
    for relative_path in CONSUMER_FILES:
        text = normalized_text(relative_path)
        for legacy_reference in LEGACY_REFERENCES:
            assert legacy_reference not in text, (
                f"{relative_path} depends on ReqSys legacy Worker Pool: "
                f"{legacy_reference}"
            )


def test_hosted_handoff_pins_the_dedicated_worker_pool_repository():
    workflow = normalized_text(".github/workflows/codex-worker-pool-handoff.yml")

    assert "repository: ericson-j-santos/engineering-worker-pool" in workflow
    assert f"WORKER_POOL_SHA: {DEDICATED_WORKER_POOL_SHA}" in workflow
    assert "ref: ${{ env.WORKER_POOL_SHA }}" in workflow
