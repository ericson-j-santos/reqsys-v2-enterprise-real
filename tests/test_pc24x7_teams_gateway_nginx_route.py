from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NGINX = ROOT / "infra/nginx/default.pc24x7-public-dev.conf"


def test_pc24x7_public_dev_exposes_only_teams_gateway_v1_to_api() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "location ^~ /v1/teams-gateway/" in raw
    block = raw.split("location ^~ /v1/teams-gateway/", 1)[1].split("}", 1)[0]
    assert "proxy_pass http://api:8000;" in block
    lines = {line.strip() for line in raw.splitlines()}
    assert "location /v1/ {" not in lines
    assert "location ^~ /v1/ {" not in lines


def test_teams_gateway_route_preserves_v1_prefix() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    block = raw.split("location ^~ /v1/teams-gateway/", 1)[1].split("}", 1)[0]
    assert "proxy_pass http://api:8000;" in block
    assert "proxy_pass http://api:8000/" not in block
