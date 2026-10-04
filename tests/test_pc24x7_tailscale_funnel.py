import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "pc24x7_tailscale_funnel.py"
SPEC = importlib.util.spec_from_file_location("pc24x7_tailscale_funnel", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_stable_url_uses_tailscale_dns_name():
    status = {"Self": {"DNSName": "noteri.tail650e07.ts.net."}}
    assert m.stable_url(status) == "https://noteri.tail650e07.ts.net"


def test_stable_url_requires_dns_name():
    try:
        m.stable_url({"Self": {}})
    except RuntimeError as exc:
        assert "DNSName" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_default_target_is_dev_gateway_port():
    assert m.DEFAULT_TARGET == "8083"
