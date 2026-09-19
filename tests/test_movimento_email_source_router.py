from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path("scripts/movimento_email_source_router.py")
SPEC = importlib.util.spec_from_file_location("movimento_email_source_router", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FakeCorporate:
    def __init__(self, dsn: str = "Driver={X};Server=sqlcorp;Encrypt=yes;TrustServerCertificate=no;"):
        self.dsn = dsn

    def read_secret(self, name: str) -> str:
        assert name == "MOVIMENTO_EMAIL_SOURCE_DSN"
        return self.dsn

    def validate_source_dsn(self, dsn: str) -> None:
        if "Encrypt=yes" not in dsn:
            raise RuntimeError("source_dsn_requires_encrypt")

    def dsn_value(self, dsn: str, key: str) -> str:
        wanted = key.casefold()
        for part in dsn.split(";"):
            if "=" not in part:
                continue
            k, value = part.split("=", 1)
            if k.strip().casefold() == wanted:
                return value.strip()
        return ""


def configured_env() -> dict[str, str]:
    return {
        "MOVIMENTO_EMAIL_SOURCE_DSN": "present",
        "MOVIMENTO_EMAIL_TARGET_DSN_FILE": "C:/protected/target.dsn",
    }


def test_auto_falls_back_when_corporate_configuration_is_missing() -> None:
    decision = module.select_route("auto", {})
    assert decision["selected_source"] == "equivalent-dev"
    assert decision["fallback_used"] is True
    assert decision["fallback_reason"] == "corporate_dsn_configuration_missing"
    assert decision["hard_block"] is None


def test_corporate_mode_fails_closed_when_configuration_is_missing() -> None:
    decision = module.select_route("corporate", {})
    assert decision["selected_source"] is None
    assert decision["hard_block"] == "corporate_dsn_configuration_missing"


def test_ambiguous_dsn_never_falls_back() -> None:
    env = configured_env()
    env["MOVIMENTO_EMAIL_SOURCE_DSN_FILE"] = "C:/protected/source.dsn"
    decision = module.select_route("auto", env)
    assert decision["selected_source"] is None
    assert decision["fallback_used"] is False
    assert decision["hard_block"] == "ambiguous_dsn_configuration"


def test_auto_falls_back_only_for_dns_unavailable_after_valid_config() -> None:
    decision = module.select_route(
        "auto",
        configured_env(),
        dns_resolver=lambda host: False,
        corporate_module=FakeCorporate(),
    )
    assert decision["selected_source"] == "equivalent-dev"
    assert decision["fallback_reason"] == "corporate_source_dns_unavailable"


def test_corporate_mode_dns_failure_is_hard_block() -> None:
    decision = module.select_route(
        "corporate",
        configured_env(),
        dns_resolver=lambda host: False,
        corporate_module=FakeCorporate(),
    )
    assert decision["selected_source"] is None
    assert decision["hard_block"] == "corporate_source_dns_unavailable"


def test_ready_corporate_source_is_selected_without_fallback() -> None:
    seen: list[str] = []
    decision = module.select_route(
        "auto",
        configured_env(),
        dns_resolver=lambda host: seen.append(host) or True,
        corporate_module=FakeCorporate("Driver={X};Server=sqlcorp\\inst01;Encrypt=yes;TrustServerCertificate=no;"),
    )
    assert seen == ["sqlcorp"]
    assert decision["selected_source"] == "corporate"
    assert decision["fallback_used"] is False
    assert decision["hard_block"] is None


def test_invalid_present_dsn_is_not_masked_by_equivalent_fallback() -> None:
    decision = module.select_route(
        "auto",
        configured_env(),
        dns_resolver=lambda host: True,
        corporate_module=FakeCorporate("Driver={X};Server=sqlcorp;Encrypt=no;"),
    )
    assert decision["selected_source"] is None
    assert decision["fallback_used"] is False
    assert decision["hard_block"]
    assert "source_dsn_requires_encrypt" in decision["hard_block"]


def test_router_source_never_promotes_equivalent_to_corporate() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert '"equivalent_source": False' in script
    assert "corporate_source_validated=False" in script
    assert "após selecionar corporate" in script
