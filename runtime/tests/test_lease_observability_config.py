import pytest

from app.core.config import RuntimeSettings


def test_lease_config_aceita_intervalo_menor_que_ttl() -> None:
    settings = RuntimeSettings(
        redis_lease_ttl_seconds=90,
        redis_lease_renew_interval_seconds=30,
    )

    assert settings.redis_lease_ttl_seconds == 90
    assert settings.redis_lease_renew_interval_seconds == 30


def test_lease_config_rejeita_intervalo_maior_ou_igual_ao_ttl() -> None:
    with pytest.raises(ValueError, match="deve ser menor"):
        RuntimeSettings(
            redis_lease_ttl_seconds=20,
            redis_lease_renew_interval_seconds=20,
        )


def test_lease_config_rejeita_ttl_inseguro() -> None:
    with pytest.raises(ValueError, match="deve ser >= 5"):
        RuntimeSettings(redis_lease_ttl_seconds=4)
