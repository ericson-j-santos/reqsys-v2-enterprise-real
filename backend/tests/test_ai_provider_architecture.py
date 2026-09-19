from __future__ import annotations

from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parents[1] / 'app'
ALLOWED_PROVIDER_PORTS = {
    Path('services/ai_provider_config.py'),
    Path('services/llm_provider.py'),
}
FORBIDDEN_PROVIDER_MARKERS = (
    'api.openai.com',
    'api.anthropic.com',
    'api.groq.com',
    'generativelanguage.googleapis.com',
    '/api/generate',
)
FORBIDDEN_SDK_MARKERS = (
    'import openai',
    'from openai ',
    'import anthropic',
    'from anthropic ',
    'import google.generativeai',
    'from groq ',
)


def test_integracoes_de_provider_nao_bypassam_porta_comum() -> None:
    violations: list[str] = []
    for path in BACKEND_APP.rglob('*.py'):
        relative = path.relative_to(BACKEND_APP)
        if relative in ALLOWED_PROVIDER_PORTS:
            continue
        content = path.read_text(encoding='utf-8')
        markers = [
            marker
            for marker in (*FORBIDDEN_PROVIDER_MARKERS, *FORBIDDEN_SDK_MARKERS)
            if marker in content
        ]
        if markers:
            violations.append(f'{relative}: {", ".join(markers)}')

    assert not violations, (
        'Integrações diretas com providers são proibidas; use AIProviderRouter/LLMGateway. '
        + '; '.join(violations)
    )
