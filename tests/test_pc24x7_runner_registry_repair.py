import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "pc24x7_runner_registry_repair.py"
SPEC = importlib.util.spec_from_file_location("pc24x7_runner_registry_repair", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class FakeRequester:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.put_bodies = []

    def __call__(self, request):
        if request.get_method() == "PUT":
            import json
            self.put_bodies.append(json.loads(request.data.decode("utf-8")))
            return {"labels": [{"name": x} for x in self.put_bodies[-1]["labels"]]}
        return self.snapshots.pop(0)


def registry(runners):
    return {"total_count": len(runners), "runners": runners}


def runner(status="online", labels=None, runner_id=77):
    labels = labels or ["self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev"]
    return {
        "id": runner_id,
        "name": "DESKTOP-PDQK954",
        "status": status,
        "busy": False,
        "labels": [{"name": x} for x in labels],
    }


def test_offline_fails_closed_without_mutation():
    fake = FakeRequester([registry([runner(status="offline")])])
    result = m.repair("token", fake)
    assert result["ok"] is False
    assert result["state"] == "runner_offline"
    assert fake.put_bodies == []


def test_missing_custom_labels_are_repaired_only_when_online():
    before = runner(labels=["self-hosted", "Windows", "X64"])
    after = runner()
    fake = FakeRequester([registry([before]), registry([after])])
    result = m.repair("token", fake)
    assert result["ok"] is True
    assert result["state"] == "runner_registry_ready"
    assert fake.put_bodies == [{"labels": ["pc24x7", "reqsys-dev"]}]


def test_missing_runner_fails_closed():
    fake = FakeRequester([registry([])])
    result = m.repair("token", fake)
    assert result["state"] == "runner_missing"
    assert result["mutated"] is False


def test_failure_output_does_not_echo_exception_details() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert '"error": str(exc)' not in source
    assert '"error_type": type(exc)' not in source
