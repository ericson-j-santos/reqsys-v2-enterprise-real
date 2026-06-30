from scripts.operational_multi_environment_evidence import build_env_entry, normalize_api_base


def test_normalize_api_base_strips_docs_suffix():
    assert normalize_api_base("https://reqsys-api-dev.fly.dev/docs") == "https://reqsys-api-dev.fly.dev"
    assert normalize_api_base("https://reqsys-api-dev.fly.dev") == "https://reqsys-api-dev.fly.dev"


def test_build_env_entry_aligns_probe_docs_with_manifest_base():
    probe = {
        "name": "desenvolvimento",
        "frontend": "https://reqsys-app-dev.fly.dev",
        "api": "https://reqsys-api-dev.fly.dev/docs",
    }
    fly_env = {
        "api_url": "https://reqsys-api-dev.fly.dev",
        "frontend_url": "https://reqsys-app-dev.fly.dev",
    }

    entry = build_env_entry("dev", probe, fly_env)

    assert entry["url_matrix_aligned"] is True
