import os
from urllib import parse, request
from urllib.error import URLError

from fastapi import APIRouter

from app.core.envelope import ok
from app.core.secrets import get_secret

router = APIRouter(prefix='/v1/relatorios', tags=['Relatorios'])

DEFAULT_REPORTS = [
    'AtvIndividual',
    'Cracha',
    'CracháAula2',
    'RelatorioDetalhado',
    'RelatorioDetalhadoAula2',
]


def _list_reports() -> list[str]:
    raw = get_secret('SSRS_REPORT_NAMES', '') or ''
    if not raw.strip():
        return DEFAULT_REPORTS
    return [item.strip() for item in raw.split(',') if item.strip()]


def _ssrs_require_https() -> bool:
    value = (get_secret('SSRS_REQUIRE_HTTPS', 'false') or 'false').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


def _normalize_ssrs_base_url(base_url: str, require_https: bool) -> str:
    if require_https and base_url.lower().startswith('http://'):
        return f"https://{base_url[7:]}"
    return base_url


def _build_ssrs_render_url(base_url: str, folder: str, report_name: str) -> str:
    clean_folder = folder.strip('/').replace(' ', '%20')
    report_path = f'/{clean_folder}/{report_name}' if clean_folder else f'/{report_name}'
    encoded = parse.quote(report_path, safe='/')
    return f"{base_url}?{encoded}&rs:Command=Render"


@router.get('/ssrs')
def ssrs_links():
    raw_base_url = (get_secret('SSRS_BASE_URL', '') or '').strip().rstrip('/')
    require_https = _ssrs_require_https()
    base_url = _normalize_ssrs_base_url(raw_base_url, require_https)
    folder = (get_secret('SSRS_REPORTS_PATH', 'ReqSys') or 'ReqSys').strip()
    reports = _list_reports()

    if not base_url:
        return ok({
            'enabled': False,
            'message': 'Configure SSRS_BASE_URL para habilitar integração SSRS.',
            'reports': [],
            'report_server_base_url': None,
            'reports_path': folder,
            'https_required': require_https,
        })

    data = []
    for name in reports:
        data.append({
            'name': name,
            'render_url': _build_ssrs_render_url(base_url, folder, name),
        })

    return ok({
        'enabled': True,
        'report_server_base_url': base_url,
        'reports_path': folder,
        'reports': data,
        'https_required': require_https,
    })


@router.get('/ssrs/health')
def ssrs_health():
    raw_base_url = (get_secret('SSRS_BASE_URL', '') or '').strip().rstrip('/')
    require_https = _ssrs_require_https()
    base_url = _normalize_ssrs_base_url(raw_base_url, require_https)
    if not base_url:
        return ok({'enabled': False, 'reachable': False, 'detail': 'SSRS_BASE_URL não configurado', 'https_required': require_https})

    try:
        req = request.Request(base_url, headers={'User-Agent': 'reqsys-ssrs-health/1.0'})
        with request.urlopen(req, timeout=5) as resp:
            status_code = resp.getcode()
        return ok({'enabled': True, 'reachable': status_code < 500, 'status_code': status_code, 'https_required': require_https})
    except URLError as exc:
        return ok({'enabled': True, 'reachable': False, 'detail': str(exc.reason), 'https_required': require_https})
