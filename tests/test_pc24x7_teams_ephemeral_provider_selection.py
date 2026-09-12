import importlib.util
import sys
from pathlib import Path


SCRIPTS = Path('scripts').resolve()
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / 'pc24x7_teams_ephemeral_e2e.py'
spec = importlib.util.spec_from_file_location('pc24x7_teams_ephemeral_provider_selection', SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_requested_provider_is_kept_when_runtime_reports_it_configured():
    provider, model, fallback = module.select_runtime_provider(
        'gemini', 'gemini-2.5-flash', ['groq', 'gemini']
    )
    assert provider == 'gemini'
    assert model == 'gemini-2.5-flash'
    assert fallback is False


def test_runtime_falls_back_to_configured_provider_with_repo_default_model():
    provider, model, fallback = module.select_runtime_provider(
        'gemini', 'gemini-2.5-flash', ['groq']
    )
    assert provider == 'groq'
    assert model == 'llama-3.3-70b-versatile'
    assert fallback is True


def test_readiness_exposes_only_sanitized_provider_names(monkeypatch):
    monkeypatch.setattr(
        module,
        'request_json',
        lambda *_args, **_kwargs: (
            200,
            {
                'data': {
                    'schema_version': '1.0.0',
                    'status': 'ready',
                    'ready': True,
                    'bloqueios': [],
                    'providers_configurados': ['Gemini', 'groq', 'gemini'],
                    'conversation_references': 1,
                }
            },
        ),
    )
    status, readiness = module.check_readiness('https://dev.invalid', 'token', 'corr')
    assert status == 200
    assert readiness['providers_configured'] == ['gemini', 'groq']
    assert readiness['secret_value_exposed'] is False
    assert 'token' not in readiness


def test_e2e_source_uses_public_classification_only_for_synthetic_probe():
    source = SCRIPT.read_text(encoding='utf-8')
    assert "data_classification='public'" in source
    assert "'data_classification': 'public'" in source
