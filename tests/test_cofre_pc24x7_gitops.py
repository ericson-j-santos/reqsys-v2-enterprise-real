from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pc24x7_cofre_overlay_versions_secret_mount_without_secret_value() -> None:
    content = (ROOT / "docker-compose.pc24x7-cofre.yml").read_text(encoding="utf-8")
    assert 'REQSYS_DATA_DIR: "/data"' in content
    assert 'reqsys-cofre-data:/data' in content
    assert '/run/secrets/cofre_keyring_passphrase' in content
    assert 'COFRE_KEYRING_PASSPHRASE_FILE' in content
    assert 'cofre-keyring-passphrase.txt' in content
    assert 'export COFRE_KEYRING_PASSPHRASE="$(cat /run/secrets/cofre_keyring_passphrase)"' in content
    assert 'COFRE_KEYRING_PASSPHRASE: "' not in content


def test_pc24x7_cofre_overlay_uses_read_from_secret_file_at_runtime() -> None:
    content = (ROOT / "docker-compose.pc24x7-cofre.yml").read_text(encoding="utf-8")
    assert 'cat /run/secrets/cofre_keyring_passphrase' in content
    assert 'export COFRE_KEYRING_PASSPHRASE=' in content
    assert 'exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload' in content


def test_e2e_executor_is_dev_only_and_sanitized() -> None:
    content = (ROOT / "scripts" / "execute_cofre_dev_runtime_e2e.py").read_text(encoding="utf-8")
    assert 'ALLOWED_ENVIRONMENTS = {"dev", "development", "desenvolvimento"}' in content
    assert '"production_touched": False' in content
    assert '"sensitive_values_exposed": False' in content
    assert 'wait_container_healthy()' in content
    assert 'scope_denial_http_403' in content


def test_recreate_executor_is_dev_scoped_and_never_reads_secret_value() -> None:
    content = (ROOT / "scripts" / "recreate_cofre_dev_pc24x7.py").read_text(encoding="utf-8")
    assert 'DEFAULT_PROJECT = "wt-pc24x7-piloto"' in content
    assert 'DEFAULT_CONTAINER = "wt-pc24x7-piloto-api-1"' in content
    assert 'cofre-keyring-passphrase.txt' in content
    assert 'args.secret_file.is_file()' in content
    assert 'args.secret_file.read_text' not in content
    assert '"--build"' in content
    assert '"--force-recreate"' in content
    assert '"api"' in content
    assert '"production_touched": False' in content
