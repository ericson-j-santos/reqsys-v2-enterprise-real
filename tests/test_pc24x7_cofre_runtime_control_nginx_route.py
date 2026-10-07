from pathlib import Path

NGINX = Path("infra/nginx/default.pc24x7-public-dev.conf")


def test_public_dev_exposes_authenticated_cofre_v1_surface_for_physical_gate() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "location ^~ /v1/cofre/ {" in raw
    block = raw.split("location ^~ /v1/cofre/ {", 1)[1].split("}", 1)[0]
    assert "limit_req zone=cofre" in block
    assert "proxy_pass http://api:8000;" in block


def test_cofre_runtime_control_route_preserves_v1_prefix() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    block = raw.split("location ^~ /v1/cofre/ {", 1)[1].split("}", 1)[0]
    assert "proxy_pass http://api:8000;" in block
    assert "proxy_pass http://api:8000/" not in block


def test_public_dev_exposes_authenticated_audit_surface_for_cofre_gate() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "location ^~ /v1/auditoria/ {" in raw
    block = raw.split("location ^~ /v1/auditoria/ {", 1)[1].split("}", 1)[0]
    assert "limit_req zone=cofre" in block
    assert "proxy_pass http://api:8000;" in block
    assert "proxy_pass http://api:8000/" not in block
