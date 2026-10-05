from pathlib import Path

NGINX = Path("infra/nginx/default.pc24x7-public-dev.conf")


def test_public_dev_exposes_only_cofre_runtime_control_v1_surface() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "location ^~ /v1/cofre/runtime/ {" in raw
    block = raw.split("location ^~ /v1/cofre/runtime/ {", 1)[1].split("}", 1)[0]
    assert "limit_req zone=cofre" in block
    assert "proxy_pass http://api:8000;" in block
    lines = {line.strip() for line in raw.splitlines()}
    assert "location /v1/cofre/ {" not in lines
    assert "location ^~ /v1/cofre/ {" not in lines


def test_cofre_runtime_control_route_preserves_v1_prefix() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    block = raw.split("location ^~ /v1/cofre/runtime/ {", 1)[1].split("}", 1)[0]
    assert "proxy_pass http://api:8000;" in block
    assert "proxy_pass http://api:8000/" not in block
