import pytest

from scripts.parse_external_wait_command import parse_command


def test_parse_valid_blocked_command():
    payload = parse_command(
        "/external-wait action=blocked category=external_provider "
        "wait_id=e2e-1685 correlation_id=reqsys-e2e sha=63da460 "
        "source_reference=pr:1685/e2e"
    )
    assert payload == {
        "action": "blocked",
        "category": "external_provider",
        "wait_id": "e2e-1685",
        "correlation_id": "reqsys-e2e",
        "sha": "63da460",
        "source_reference": "pr:1685/e2e",
    }


def test_parse_valid_unblocked_without_optional_fields():
    payload = parse_command(
        "/external-wait action=unblocked category=human_gate "
        "wait_id=wait-1 correlation_id=corr-1"
    )
    assert payload["action"] == "unblocked"
    assert payload["sha"] is None
    assert payload["source_reference"] is None


@pytest.mark.parametrize(
    "command,error",
    [
        ("/other action=blocked category=external_provider wait_id=w correlation_id=c", "command_prefix_invalid"),
        ("/external-wait action=blocked category=external_provider wait_id=w", "command_required_missing:correlation_id"),
        ("/external-wait action=other category=external_provider wait_id=w correlation_id=c", "action_invalid"),
        ("/external-wait action=blocked category=other wait_id=w correlation_id=c", "category_invalid"),
        ("/external-wait action=blocked category=external_provider wait_id=w correlation_id=c sha=xyz", "sha_invalid"),
        ("/external-wait action=blocked action=unblocked category=external_provider wait_id=w correlation_id=c", "command_key_duplicate:action"),
        ("/external-wait action=blocked category=external_provider wait_id=w correlation_id=c extra=x", "command_key_unknown:extra"),
    ],
)
def test_parse_rejects_invalid_commands(command, error):
    with pytest.raises(ValueError, match=error):
        parse_command(command)


def test_parse_rejects_source_reference_with_spaces():
    with pytest.raises(ValueError, match="source_reference_invalid"):
        parse_command(
            "/external-wait action=blocked category=external_provider "
            "wait_id=w correlation_id=c source_reference='contains space'"
        )
