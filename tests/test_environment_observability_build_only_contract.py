from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROMOTION = (ROOT / ".github/workflows/environment-observability-promotion.yml").read_text(encoding="utf-8")
GATEWAY = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text(encoding="utf-8")


def test_promotion_preserves_build_only_and_blocks_retired_fly_deploy() -> None:
    assert "build_only:" in PROMOTION
    assert "default: false" in PROMOTION
    assert "type: boolean" in PROMOTION
    jobs = yaml.safe_load(PROMOTION)["jobs"]
    for name in ("deploy-development", "deploy-staging", "deploy-production"):
        condition = jobs[name]["if"]
        assert condition.startswith("${{ false && (")
        assert "!inputs.build_only" in condition
    assert jobs["validate-and-publish"].get("if") != "${{ false }}"


def test_build_only_still_publishes_immutable_ghcr_image_and_evidence() -> None:
    assert "Build and publish once" in PROMOTION
    assert "push: true" in PROMOTION
    assert "provenance: true" in PROMOTION
    assert "sbom: true" in PROMOTION
    assert "${{ steps.image.outputs.ref }}:${{ github.sha }}" in PROMOTION
    assert '\"digest\": \"${{ steps.build.outputs.digest }}\"' in PROMOTION
    assert '\"build_only\": \"${{ inputs.build_only }}\" == \"true\"' in PROMOTION


def test_gateway_dispatches_only_build_only_development_mode() -> None:
    assert "github.event.comment.body == '/reqsys run environment-observability-build-only-dev'" in GATEWAY
    assert "target='environment-observability-promotion.yml'" in GATEWAY
    assert "mode='build-only'" in GATEWAY
    assert "-f promote_to=development" in GATEWAY
    assert "-f build_only=true" in GATEWAY
    assert "-f image=" not in GATEWAY
    assert "-f digest=" not in GATEWAY


def test_environment_observability_build_only_is_not_self_hosted() -> None:
    assert "steps.route.outputs.target == 'environment-observability-promotion.yml'" not in GATEWAY
