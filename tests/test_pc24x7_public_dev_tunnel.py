import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "pc24x7_public_dev_tunnel.py"
SPEC = importlib.util.spec_from_file_location("pc24x7_public_dev_tunnel", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_extract_quick_urls_deduplicates_and_preserves_order():
    text = (
        "https://alpha-one.trycloudflare.com x "
        "https://beta-two.trycloudflare.com y "
        "https://alpha-one.trycloudflare.com"
    )
    assert m.extract_quick_urls(text) == [
        "https://alpha-one.trycloudflare.com",
        "https://beta-two.trycloudflare.com",
    ]


def test_container_matches_accepts_canonical_runtime():
    state = {
        "running": True,
        "args": ["--no-autoupdate", "tunnel", "--url", m.DEFAULT_TARGET],
        "restart": "unless-stopped",
        "image": m.DEFAULT_IMAGE,
    }
    assert m.container_matches(state, target=m.DEFAULT_TARGET, image=m.DEFAULT_IMAGE)


def test_container_matches_rejects_stale_lan_ip():
    state = {
        "running": True,
        "args": ["--no-autoupdate", "tunnel", "--url", "http://192.168.1.45:8081"],
        "restart": "unless-stopped",
        "image": m.DEFAULT_IMAGE,
    }
    assert not m.container_matches(state, target=m.DEFAULT_TARGET, image=m.DEFAULT_IMAGE)


def test_build_run_command_uses_host_docker_internal():
    command = m.build_run_command(
        "reqsys-dev-gateway-tunnel",
        target=m.DEFAULT_TARGET,
        image=m.DEFAULT_IMAGE,
    )
    assert m.DEFAULT_TARGET in command
    assert "--restart" in command
    assert "unless-stopped" in command


def test_public_access_manifest_has_no_required_fly_targets():
    manifest = json.loads((ROOT / "infra" / "public-access-urls.json").read_text(encoding="utf-8"))
    serialized = json.dumps(manifest).lower()
    assert "fly.dev" not in serialized
    assert not any(
        target.get("provider") == "fly" and target.get("required") is not False
        for target in manifest["targets"]
    )


def test_tunnel_requires_complete_runtime_and_static_frontend() -> None:
    raw = MODULE.read_text(encoding="utf-8")
    assert "/api/runtime/health" in raw
    assert "/api/runtime/readiness" in raw
    assert "/api/runtime/build-info" in raw
    assert "/task-console" in raw
    assert "/@vite/client" in raw
    assert 'vite_client.get("status") == 404' in raw
