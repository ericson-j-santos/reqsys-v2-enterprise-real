from datetime import datetime, timezone
from urllib import parse

import urllib3
import requests as _requests
from requests_ntlm import HttpNtlmAuth

try:
    from requests_negotiate_sspi import HttpNegotiateAuth as _HttpNegotiateAuth
    _SSPI_AVAILABLE = True
except ImportError:  # não disponível em Linux/Docker
    _HttpNegotiateAuth = None
    _SSPI_AVAILABLE = False

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.envelope import ok
from app.core.secrets import get_secret

# Suprime aviso de certificado auto-assinado para chamadas internas ao SSRS
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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


def _get_ssrs_auth():
    """Retorna auth para SSRS: NTLM explícito se SSRS_USER/SSRS_PASSWORD configurados,
    senão Negotiate/SSPI usando credenciais da sessão Windows atual."""
    user = (get_secret('SSRS_USER', '') or '').strip()
    password = (get_secret('SSRS_PASSWORD', '') or '').strip()
    if user and password:
        return HttpNtlmAuth(user, password)
    # Autenticação Windows SSO via SSPI (sem necessidade de senha no .env)
    if _SSPI_AVAILABLE:
        return _HttpNegotiateAuth()

    # Em ambientes sem SSPI (ex: Linux CI), o backend deve falhar de forma
    # controlada (testes/contratos) e não explodir com RuntimeError.
    raise HTTPException(
        status_code=503,
        detail='SSRS auth indisponível neste ambiente (configure SSRS_USER/SSRS_PASSWORD ou habilite SSPI).',
    )



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

    auth = _get_ssrs_auth()
    user = (get_secret('SSRS_USER', '') or '').strip()
    auth_mode = 'ntlm' if user else 'sspi'

    try:
        resp = _requests.get(
            base_url,
            auth=auth,
            timeout=5,
            verify=False,  # aceita certificado interno auto-assinado
            headers={'User-Agent': 'reqsys-ssrs-health/1.0'},
        )
        return ok({
            'enabled': True,
            'reachable': resp.status_code < 500,
            'status_code': resp.status_code,
            'https_required': require_https,
            'auth_mode': auth_mode,
        })
    except _requests.exceptions.RequestException as exc:
        return ok({'enabled': True, 'reachable': False, 'detail': str(exc), 'https_required': require_https, 'auth_mode': auth_mode})


def _build_ssrs_pdf_url(base_url: str, folder: str, report_name: str) -> str:
    clean_folder = folder.strip('/').replace(' ', '%20')
    report_path = f'/{clean_folder}/{report_name}' if clean_folder else f'/{report_name}'
    encoded = parse.quote(report_path, safe='/')
    return f"{base_url}?{encoded}&rs:Format=PDF&rs:Command=Render"


def _check_report_accessibility(render_url: str, auth):
    """Valida acessibilidade de relatório com fallback de HEAD para GET.

    Alguns ambientes SSRS bloqueiam HEAD e retornam 405/501 apesar de o relatório
    estar acessível via GET.
    """
    resp = _requests.head(
        render_url,
        auth=auth,
        timeout=5,
        verify=False,
        allow_redirects=True,
        headers={'User-Agent': 'reqsys-ssrs-status/1.0'},
    )

    if resp.status_code in {405, 501}:
        get_resp = _requests.get(
            render_url,
            auth=auth,
            timeout=5,
            verify=False,
            allow_redirects=True,
            stream=True,
            headers={'User-Agent': 'reqsys-ssrs-status/1.0'},
        )
        get_resp.close()
        return get_resp.status_code

    return resp.status_code


@router.get('/ssrs/status')
def ssrs_status():
    """Retorna status de acessibilidade de cada relatório SSRS (HEAD request por relatório)."""
    raw_base_url = (get_secret('SSRS_BASE_URL', '') or '').strip().rstrip('/')
    require_https = _ssrs_require_https()
    base_url = _normalize_ssrs_base_url(raw_base_url, require_https)
    folder = (get_secret('SSRS_REPORTS_PATH', 'ReqSys') or 'ReqSys').strip()
    reports = _list_reports()
    checked_at = datetime.now(timezone.utc).isoformat()

    if not base_url:
        return ok({
            'enabled': False,
            'checked_at': checked_at,
            'reports': [],
        })

    auth_error = None
    try:
        auth = _get_ssrs_auth()
    except HTTPException as exc:
        # Em ambientes sem SSPI/credenciais (ex.: CI Linux), mantemos o contrato
        # de resposta 200 para /ssrs/status e marcamos cada relatório como offline.
        auth = None
        auth_error = exc.detail

    items = []
    for name in reports:
        render_url = _build_ssrs_render_url(base_url, folder, name)
        pdf_url = _build_ssrs_pdf_url(base_url, folder, name)
        if auth_error:
            accessible = False
            status_code = None
            detail = auth_error
        else:
            try:
<<<<<<< Updated upstream
                resp = _requests.head(
                    render_url,
                    auth=auth,
                    timeout=5,
                    verify=False,
                    allow_redirects=True,
                    headers={'User-Agent': 'reqsys-ssrs-status/1.0'},
                )
                accessible = resp.status_code < 400
                status_code = resp.status_code
=======
                status_code = _check_report_accessibility(render_url, auth)
                accessible = status_code < 400
>>>>>>> Stashed changes
                detail = None
            except _requests.exceptions.RequestException as exc:
                accessible = False
                status_code = None
                detail = str(exc)

        items.append({
            'name': name,
            'accessible': accessible,
            'status_code': status_code,
            'detail': detail,
            'render_url': render_url,
            'pdf_download_path': f'/v1/relatorios/ssrs/{parse.quote(name, safe="")}/pdf',
        })

    total = len(items)
    online = sum(1 for r in items if r['accessible'])
    return ok({
        'enabled': True,
        'checked_at': checked_at,
        'summary': {'total': total, 'online': online, 'offline': total - online},
        'reports': items,
    })


@router.get('/ssrs/{nome}/pdf')
def ssrs_pdf_download(nome: str):
    """Proxy de download do PDF do relatório via backend (autenticação Windows transparente)."""
    raw_base_url = (get_secret('SSRS_BASE_URL', '') or '').strip().rstrip('/')
    require_https = _ssrs_require_https()
    base_url = _normalize_ssrs_base_url(raw_base_url, require_https)

    if not base_url:
        raise HTTPException(status_code=503, detail='SSRS_BASE_URL não configurado')

    folder = (get_secret('SSRS_REPORTS_PATH', 'ReqSys') or 'ReqSys').strip()
    allowed = _list_reports()

    # Valida que o nome solicitado é um relatório cadastrado (evita SSRF aberto)
    if nome not in allowed:
        raise HTTPException(status_code=404, detail=f'Relatório "{nome}" não encontrado no catálogo')

    pdf_url = _build_ssrs_pdf_url(base_url, folder, nome)
    
    try:
        auth = _get_ssrs_auth()
    except HTTPException as exc:
        # Em ambientes sem SSPI/credenciais, retorna o erro apropriado
        raise exc

    try:
        resp = _requests.get(
            pdf_url,
            auth=auth,
            timeout=30,
            verify=False,
            stream=True,
            headers={'User-Agent': 'reqsys-ssrs-pdf/1.0'},
        )
    except _requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f'Erro ao contatar SSRS: {exc}')

    if resp.status_code == 401:
        raise HTTPException(status_code=502, detail='SSRS retornou 401 — verifique credenciais NTLM/SSPI')
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f'SSRS retornou {resp.status_code}')

    safe_name = nome.replace('/', '_').replace('\\', '_')
    filename = f"{safe_name}.pdf"

    def iter_content():
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    return StreamingResponse(
        iter_content(),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store',
        },
    )
