"""Gateway nginx da stack Docker × rotas do backend registradas com o prefixo `/api` literal.

Achado do piloto PC 24x7 (2026-09-10): `location /api/ { proxy_pass http://api:8000/; }`
remove o prefixo, então `/api/runtime/health` chegava ao backend como `/runtime/health`
e respondia 404 — inclusive para o comando de verificação do próprio runbook.
"""

import re
from pathlib import Path

NGINX_CONFS = [
    Path('infra/nginx/default.dev.conf'),
    Path('infra/nginx/default.prod.conf'),
    Path('infra/nginx/default.local.conf'),
    Path('infra/nginx/default.conf'),
]
# Prefixos que o backend registra literalmente com `/api/...` (ver `@app.get('/api/runtime/...')`
# em backend/app/main.py e os routers com `prefix='/api/...'`).
PREFIXOS_LITERAIS = [
    'runtime', 'requisitos', 'operational-autonomy', 'integracoes', 'govbi', 'rag', 'connectors', 'workflows',
]
COMPOSE = Path('docker-compose.yml')
RUNBOOK = Path('docs/runbooks/pc24x7-piloto-dev.md')


def _literal_location(conf: str) -> str:
    match = re.search(r'location ~ \^/api/\(([^)]+)\)\(/\|\$\) \{\s*proxy_pass (\S+);', conf)
    assert match, 'location regex para prefixos /api literais ausente'
    prefixos = match.group(1).split('|')
    assert sorted(prefixos) == sorted(PREFIXOS_LITERAIS)
    upstream = match.group(2)
    # proxy_pass sem URI: o request URI original (com /api/) é repassado inteiro.
    assert not upstream.endswith('/'), upstream
    return upstream


def test_nginx_confs_preservam_prefixo_api_literal() -> None:
    for path in NGINX_CONFS:
        conf = path.read_text(encoding='utf-8')
        upstream = _literal_location(conf)
        # A regra literal precisa vir antes do strip genérico e usar o mesmo upstream.
        assert conf.index('location ~ ^/api/(') < conf.index('location /api/ {'), path
        assert f'proxy_pass {upstream}/;' in conf, path
        # Páginas HTML sem prefixo /api continuam acessíveis via gateway.
        assert f'location = /api/runtime {{\n    proxy_pass {upstream}/runtime;' in conf, path
        assert f'location = /api/runtime/evidence {{\n    proxy_pass {upstream}/runtime/evidence;' in conf, path


def test_backend_nao_registra_prefixo_api_literal_fora_da_lista() -> None:
    encontrados: set[str] = set()
    for arquivo in Path('backend/app').rglob('*.py'):
        texto = arquivo.read_text(encoding='utf-8')
        for prefixo in re.findall(r"@(?:app|router)\.(?:get|post|put|delete|patch)\('/api/([^/']+)", texto):
            encontrados.add(prefixo)
        for prefixo in re.findall(r"APIRouter\(prefix='/api/([^/']+)", texto):
            encontrados.add(prefixo)
    faltando = encontrados - set(PREFIXOS_LITERAIS)
    assert not faltando, f'novos prefixos /api literais sem regra no gateway: {sorted(faltando)}'


def test_compose_repassa_variaveis_da_ia_para_a_api() -> None:
    compose = COMPOSE.read_text(encoding='utf-8')
    for var in ('GEMINI_API_KEY', 'GEMINI_MODEL', 'GROQ_API_KEY', 'GROQ_MODEL'):
        assert f'- {var}=${{{var}:-' in compose, var


def test_runbook_documenta_lacunas_encontradas_no_piloto() -> None:
    runbook = RUNBOOK.read_text(encoding='utf-8')
    assert 'build: ../../kb' in runbook
    assert 'GEMINI_API_KEY' in runbook
    assert 'curl http://localhost:8081/api/runtime/health' in runbook
    assert 'compose.pc24x7-local.yml' in runbook
