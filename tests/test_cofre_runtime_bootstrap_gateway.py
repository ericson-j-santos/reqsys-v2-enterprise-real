from pathlib import Path

GATEWAY = Path(".github/workflows/reqsys-authorized-actions-gateway.yml")


def test_gateway_allowlists_exact_cofre_runtime_bootstrap_command() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    command = "/reqsys run cofre-runtime-service-token-bootstrap"
    assert f"github.event.comment.body == '{command}'" in raw
    assert f"'{command}')" in raw
    assert "target='pc24x7-teams-token-bootstrap.yml'" in raw
    assert "mode='cofre-runtime'" in raw


def test_gateway_dispatches_only_allowlisted_bootstrap_modes() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    assert 'TARGET_WORKFLOW" = "pc24x7-teams-token-bootstrap.yml' in raw
    assert "teams|cofre-runtime" in raw
    assert '-f mode="$TARGET_MODE"' in raw
    assert "pc24x7_token_bootstrap_mode_not_allowlisted" in raw
