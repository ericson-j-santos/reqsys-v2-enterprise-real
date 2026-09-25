import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = _load("noteri_desktop_runner_bootstrap", "scripts/noteri_desktop_runner_bootstrap.py")
pickup = _load("desktop_runner_pickup_evidence", "scripts/desktop_runner_pickup_evidence.py")


class FakeControlPlane:
    def __init__(self):
        self.refresh_done = False
        self.submissions = []

    def worker(self):
        safe = [
            "host.inventory.files.v1",
            "host.orchestrator.refresh.v1",
            "host.github_runner.recover.v1",
        ]
        if self.refresh_done:
            safe.append("host.github_runner.bootstrap.v1")
        return {
            "worker_id": "desktop-pdqk954",
            "device_name": "DESKTOP-PDQK954",
            "fresh": True,
            "eligible": True,
            "controller_version": "0.2.53",
            "capabilities": {
                "recovery_contract_version": 1,
                "safe_task_types": safe,
            },
        }

    def __call__(self, method, path, payload=None):
        if method == "GET" and path == "/v1/workers":
            return {"workers": [self.worker()]}
        if method == "POST" and path == "/v1/work-items":
            self.submissions.append(payload)
            task_type = payload["task_type"]
            if task_type == bootstrap.REFRESH_TASK:
                return {"created": True, "item": {"id": "refresh-1"}}
            if task_type == bootstrap.BOOTSTRAP_TASK:
                return {"created": True, "item": {"id": "bootstrap-1"}}
        if method == "GET" and path == "/v1/work-items/refresh-1":
            self.refresh_done = True
            return {
                "item": {
                    "id": "refresh-1",
                    "status": "CONCLUÍDO",
                    "result": {"expected_sha": bootstrap.EXPECTED_ORCHESTRATOR_SHA},
                }
            }
        if method == "GET" and path == "/v1/work-items/bootstrap-1":
            return {
                "item": {
                    "id": "bootstrap-1",
                    "status": "CONCLUÍDO",
                    "result": {
                        "local_listener_verified": True,
                        "pickup_required": True,
                        "secrets_read": False,
                        "production_touched": False,
                        "runner_home": "C:/actions-runner",
                    },
                }
            }
        raise AssertionError((method, path, payload))


def test_recovery_is_fixed_to_noteri_desktop_and_exact_orchestrator_sha(tmp_path):
    fake = FakeControlPlane()
    evidence_path = tmp_path / "evidence.json"
    result = bootstrap.recover(
        confirm=bootstrap.CONFIRM,
        correlation_id="desktop-runner-test-001",
        evidence_file=evidence_path,
        request=fake,
        sleep_fn=lambda _: None,
        source_host="Noteri",
        platform="nt",
    )
    assert result["ok"] is True
    assert result["expected_orchestrator_sha"] == "4dbc927595a40fc2fd6b207c0d53fd6e895049ae"
    assert result["bootstrap_capability_readback"] is True
    assert result["local_listener_verified"] is True
    assert result["github_pickup_required"] is True
    assert result["untrusted_runner_home_ignored"] is True
    assert result["remote_shell_used"] is False
    assert result["rdc_used"] is False
    assert result["wmi_used"] is False
    assert len(fake.submissions) == 2
    assert fake.submissions[0]["payload"] == {
        "target_host": "DESKTOP-PDQK954",
        "expected_sha": "4dbc927595a40fc2fd6b207c0d53fd6e895049ae",
    }
    assert fake.submissions[1]["payload"]["target_host"] == "DESKTOP-PDQK954"
    assert fake.submissions[1]["payload"]["runner_home"] == "C:/untrusted-must-be-ignored"


def test_recovery_fails_closed_for_wrong_source_or_confirmation(tmp_path):
    for confirm, host in [
        ("WRONG", "Noteri"),
        (bootstrap.CONFIRM, "OTHER-HOST"),
    ]:
        try:
            bootstrap.recover(
                confirm=confirm,
                correlation_id="desktop-runner-test-002",
                evidence_file=tmp_path / "evidence.json",
                request=FakeControlPlane(),
                sleep_fn=lambda _: None,
                source_host=host,
                platform="nt",
            )
        except bootstrap.RecoveryError:
            pass
        else:
            raise AssertionError("fail-closed validation did not reject invalid input")


def test_pickup_requires_exact_desktop_host():
    good = pickup.prove(
        pickup.CONFIRM,
        "desktop-runner-pickup-001",
        host="DESKTOP-PDQK954",
        platform="nt",
    )
    assert good["github_runner_pickup_proven"] is True
    try:
        pickup.prove(
            pickup.CONFIRM,
            "desktop-runner-pickup-002",
            host="Noteri",
            platform="nt",
        )
    except pickup.PickupError:
        pass
    else:
        raise AssertionError("pickup proof accepted the wrong host")


def test_workflow_contract_uses_governed_two_stage_physical_e2e():
    raw = (ROOT / ".github/workflows/noteri-desktop-runner-bootstrap.yml").read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "needs: recover" in raw
    assert "RULES_SHA: 881d9ca2f8e77025edb7298b22981109c567a730" in raw
    assert "4dbc927595a40fc2fd6b207c0d53fd6e895049ae" in raw
    assert "RECOVER-DESKTOP-GITHUB-RUNNER-VIA-CONTROL-PLANE" in raw
    assert "PROVE-DESKTOP-GITHUB-RUNNER-PICKUP" in raw
    assert "runner.temp" in raw
    assert '"--risk", "2"' in raw
    assert '"--risk", "1"' in raw
    assert "schtasks" not in raw.lower()
    assert "remote-desktop" not in raw.lower()
    assert "wmi" not in raw.lower()
