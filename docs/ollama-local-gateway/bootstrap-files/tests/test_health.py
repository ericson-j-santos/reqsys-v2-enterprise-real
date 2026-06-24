from reqsys_ollama_gateway.config import load_settings


def test_load_settings_defaults() -> None:
    settings = load_settings()

    assert settings.env == "dev"
    assert settings.auth_required is True
    assert settings.ollama_base_url.startswith("http")
