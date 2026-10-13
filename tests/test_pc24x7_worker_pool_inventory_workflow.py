"""Validate fixed owner workflow and nonmutating SQLite inventory scope."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "codex-worker-pool-smoke-dev.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"
SCRIPT = ROOT / "scripts" / "pc24x7_worker_pool_inventory_dev.py"


def test_governed_inventory_is_fixed_and_no_new_workflow():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")
    assert "          - inventory-read" in workflow
    assert "  inventory-read:" in workflow
    inventory = workflow.split("  inventory-read:", maxsplit=1)[1]
    assert "if: ${{ inputs.mode == 'inventory-read' }}" in inventory
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in inventory
    assert "DESKTOP-PDQK954" in inventory
    assert "session_launcher.py" in inventory
    assert "--require-runner-version-preflight" in inventory
    assert "SESSION_LAUNCH_OK" in inventory
    assert "command_gateway.py" in inventory
    assert "pc24x7_worker_pool_inventory_dev.py" in inventory
    assert "READ-WORKER-POOL-DEV-SQL-ONLY" in inventory
    assert "WORKER_POOL_PHYSICAL_INVENTORY_READ_OK" in inventory
    assert "INVENTORY_READ_ONLY_OR_DB_INVALID" in inventory
    assert "Upload sanitized readonly inventory" in inventory
    assert "if-no-files-found: error" in inventory
    assert "docker compose" not in inventory
    assert "docker rm" not in inventory

    command = "/reqsys run pc24x7-worker-pool-inventory-dev"
    assert f"github.event.comment.body == '{command}'" in gateway
    assert f"'{command}')" in gateway
    assert "github.event.issue.number == 1705" in gateway
    assert "github.event.comment.user.login == 'ericson-j-santos'" in gateway
    assert "mode='inventory-read'" in gateway
    assert "-f mode=inventory-read" in gateway
    assert "-f task_id=" not in gateway
    assert "-f worker_id=" not in gateway


def test_sqlite_inventory_cannot_mutate_or_export_secrets():
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'PRAGMA query_only=ON' in script
    assert '?mode=ro' in script
    assert "PRAGMA quick_check(1)" in script
    assert '"--user", "reqsys"' in script
    assert '"ps"' in script and '"inspect"' in script and '"exec"' in script
    assert '"run", "--detach"' not in script
    assert '"docker", "compose"' not in script
    assert '"mode=rw"' not in script
    assert "import getpass" not in script
    assert "claim_performed" in script
    assert "requeue_performed" in script
    assert "secrets_exposed" in script
    assert "container_image_id_sha256" in script
    assert "id_hash_prefix" in script
    assert "lease_token" not in script
