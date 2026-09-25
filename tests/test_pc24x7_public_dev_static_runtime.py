from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reconcile_pc24x7_public_dev_runtime.py"
OVERLAY = ROOT / "docker-compose.pc24x7-public-dev.yml"
NGINX = ROOT / "infra" / "nginx" / "default.pc24x7-public-dev.conf"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-study-mode-dev-reconcile.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def _load():
    spec = importlib.util.spec_from_file_location("pc24x7_public_dev_reconcile", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overlay_uses_production_frontend_build_and_same_sha() -> None:
    raw = OVERLAY.read_text(encoding="utf-8")
    assert "dockerfile: Dockerfile.prod" in raw
    assert "VITE_API_URL: /api" in raw
    assert "GITHUB_SHA: ${REQSYS_BUILD_SHA:?REQSYS_BUILD_SHA is required}" in raw
    assert "npm run dev" not in raw


def test_public_gateway_uses_static_frontend_and_blocks_vite_hmr() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "proxy_pass http://frontend:80" in raw
    assert "frontend:5173" not in raw
    assert "location = /@vite/client" in raw
    assert "location ^~ /src/" in raw
    assert "return 404;" in raw
    assert "max-age=31536000, immutable" in raw


def test_reconciler_is_dev_only_fast_forward_and_recreates_only_public_surface() -> None:
    module = _load()
    raw = SCRIPT.read_text(encoding="utf-8")
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.DEV_API_PORT == "8210"
    assert module.DEV_GATEWAY_PORT == "8083"
    assert '"merge", "--ff-only", expected' in raw
    assert 'reset", "--hard' not in raw
    assert '"--no-deps"' in raw
    assert '"api",' in raw and '"frontend",' in raw and '"nginx",' in raw
    assert "environment_must_be_dev" in raw
    assert "non_dev_runtime_target_blocked" in raw


def test_reconciler_requires_same_sha_static_frontend_and_negative_vite_control() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert "/api/runtime/health" in raw
    assert "/api/runtime/readiness" in raw
    assert "/api/runtime/build-info" in raw
    assert "/task-console" in raw
    assert "/@vite/client" in raw
    assert 'vite["status"] == 404' in raw
    assert '"/assets/" in html' in raw
    assert '"/src/main.js" not in html' in raw
    assert "direct_sha == expected" in raw
    assert "gateway_sha == expected" in raw


def test_workflow_has_physical_then_independent_public_evidence() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "public-static" in raw
    assert "Reconcile full DEV runtime and static frontend" in raw
    assert "pc24x7_public_dev_tunnel.py --apply" in raw
    assert "pc24x7_dev_locator_publisher.py" in raw
    assert "needs: reconcile" in raw
    assert "Independent public same-SHA smoke" in raw
    assert "vite_hmr_exposed" in raw
    assert "production_touched" in raw


def test_authorized_gateway_exposes_only_exact_static_reconcile_command() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run pc24x7-public-dev-reconcile'" in raw
    assert "'/reqsys run pc24x7-public-dev-reconcile')" in raw
    assert "target='noteri-study-mode-dev-reconcile.yml'" in raw
    assert "mode='public-static'" in raw
    assert "-f mode=public-static" in raw
    assert "-f environment=prod" not in raw
