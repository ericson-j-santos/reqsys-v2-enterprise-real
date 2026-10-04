import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location("backup_metadata", Path(__file__).parents[1] / "scripts" / "noteri_dev_backup_metadata.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def test_other_host_is_rejected_before_backup_access(monkeypatch):
    monkeypatch.setattr(module.socket, "gethostname", lambda: "wrong-host")
    monkeypatch.setattr(Path, "read_text", lambda *a, **k: pytest.fail("must not read files"))
    with pytest.raises(RuntimeError, match="NOTERI_HOST_MISMATCH"):
        module.collect()
