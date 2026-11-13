"""E2E do painel estático em Chromium, sem navegar nem disparar rede.

Não substitui E2E físico dos hosts nem o teste HTTP do site publicado.
"""
import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def page():
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    html = html.replace('<link rel="stylesheet" href="./styles.css">', '')
    html = html.replace('<script defer src="./app.js"></script>', '')
    assert 'app.js' not in html, 'Recurso de script inesperado'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                     args=['--no-sandbox', '--disable-dev-shm-usage'])
        ctx = browser.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
        p = ctx.new_page()
        errors, requests = [], []
        p.on('pageerror', lambda err: errors.append(str(err)))
        p.on('request', lambda req: requests.append(req.url))
        p.set_content(html, wait_until='load')
        p.add_style_tag(content=(ROOT / 'styles.css').read_text(encoding='utf-8'))
        p.add_script_tag(content=(ROOT / 'app.js').read_text(encoding='utf-8'))
        yield p
        assert not errors, f'Erros JavaScript: {errors}'
        assert not requests, f'Rede inesperada: {requests}'
        browser.close()

def navegar(p, vista):
    p.locator(f'.navitem[data-view="{vista}"]').click()

def confirmar(p, palavra='CONFIRMAR'):
    assert p.locator('#confirmDialog').is_visible()
    assert p.locator('#confirmOk').is_disabled()
    p.locator('#confirmInput').fill(palavra)
    assert p.locator('#confirmOk').is_enabled()
    p.locator('#confirmOk').click()

def test_abertura_offline_sem_prova_fisica(page):
    assert page.title() == 'ReqSys · Validação física'
    assert 'Sem comprovação física' in page.locator('.notice').inner_text()
    assert page.evaluate('ReqSysPainelTeste.total()') == 10
    assert page.evaluate('ReqSysPainelTeste.accepted()') == 0
    assert page.evaluate('ReqSysPainelTeste.hostReadyVerified()') == 0
    assert page.locator('.navitem').count() == 7
    for vista in ['queue', 'hosts', 'cycle', 'evidence', 'timeline', 'safety']:
        navegar(page, vista)
        assert page.locator('#screen').inner_text().strip()

def test_fila_sha_invalido_cancelamento_e_registro(page):
    navegar(page, 'queue')
    assert page.locator('.data-table tbody tr').count() == 5
    page.locator('[data-edit-task="P0-01"]').click()
    form = page.locator('#taskForm')
    form.locator('[name="confirmedSha"]').fill('INVALIDO')
    form.locator('button[type="submit"]').click()
    assert 'SHA deve ter 40 caracteres' in page.locator('.toast').inner_text()
    assert not page.locator('#confirmDialog').is_visible()
    form.locator('[name="confirmedSha"]').fill('a'*40)
    form.locator('[name="nextAction"]').fill('Checagem declarada')
    form.locator('button[type="submit"]').click()
    page.locator('#confirmDialog button[value="cancel"]').click()
    assert page.evaluate('ReqSysPainelTeste.state().tasks[0].nextAction') != 'Checagem declarada'
    form.locator('button[type="submit"]').click()
    confirmar(page)
    page.wait_for_function("ReqSysPainelTeste.state().tasks[0].confirmedSha === 'a'.repeat(40)")
    assert page.evaluate('ReqSysPainelTeste.state().tasks[0].confirmedSha') == 'a'*40
    assert page.evaluate('ReqSysPainelTeste.accepted()') == 0

def test_host_preenchido_nao_se_torna_homologado(page):
    navegar(page, 'hosts')
    assert page.locator('.host-card').count() == 3
    page.locator('[data-edit-host="DESKTOP-PDQK954"]').click()
    form = page.locator('#hostForm')
    form.locator('[name="physicalId"]').fill('Inventário apenas declarado')
    form.locator('[name="labels"]').fill('pc24x7,desktop-runtime,runtime-dev')
    form.locator('[name="observedSha"]').fill('b'*40)
    for chave in ['normal', 'session', 'validated', 'gateway', 'runner', 'network']:
        form.locator(f'[name="{chave}"]').check()
    form.locator('[name="worktree"]').fill('isolado')
    form.locator('[name="lease"]').fill('exclusivo')
    form.locator('button[type="submit"]').click()
    confirmar(page)
    assert page.evaluate('ReqSysPainelTeste.hostReadyVerified()') == 0
    assert page.locator('.host-card').first.locator('text=Não comprovado').count() >= 1

def test_evento_e_checkpoint_nao_aumentam_aceite(page):
    navegar(page, 'cycle')
    assert page.locator('.step-card').count() == 10
    page.locator('[data-record-step="4"]').click()
    form = page.locator('#eventForm')
    form.locator('[name="title"]').fill('Registro local, não prova')
    form.locator('[name="kind"]').select_option('pickup')
    form.locator('[name="sha"]').fill('inválido')
    form.locator('button[type="submit"]').click()
    assert 'SHA de commit exige 40 caracteres' in page.locator('.toast').inner_text()
    assert page.evaluate('ReqSysPainelTeste.state().events.length') == 0
    form.locator('[name="sha"]').fill('c'*40)
    form.locator('[name="artifactHash"]').fill('d'*64)
    form.locator('[name="result"]').fill('Só registro local')
    form.locator('button[type="submit"]').click()
    confirmar(page)
    page.wait_for_function('ReqSysPainelTeste.documents() === 1')
    assert page.evaluate('ReqSysPainelTeste.documents()') == 1
    assert page.evaluate('ReqSysPainelTeste.accepted()') == 0
    navegar(page, 'timeline')
    assert 'Registro local, não prova' in page.locator('#timelineResults').inner_text()

def test_exportacao_local_sem_rede(page):
    navegar(page, 'safety')
    with page.expect_download() as download:
        page.locator('#exportAgain').click()
    item = download.value
    assert item.suggested_filename == 'reqsys-validacao-fisica.json'
    payload = json.loads(Path(item.path()).read_text())
    assert len(payload['tasks']) == 5
    assert 'não autenticados' in payload['exportCaveat']
    with page.expect_download() as download_md:
        page.locator('#exportMd').click()
    assert download_md.value.suggested_filename.endswith('.md')

def test_responsivo_sem_rolagem_horizontal(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    navegar(page, 'hosts')
    assert page.locator('.host-card').count() == 3
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')

def test_importacao_html_malicioso_nao_executa_script(page):
    """Entrada externa continua texto: nenhuma tag/handler pode ser executada."""
    payload = page.evaluate('ReqSysPainelTeste.state()')
    ataque = '<img src=x onerror="window.__ataque=1"><script>window.__ataque=1</script>'
    payload['events'] = [{
        'id': 'EV-NEG', 'title': ataque, 'kind': 'diagnostico',
        'at': '2026-11-13T10:00:00Z', 'step': 1, 'host': 'Noteri',
        'command': ataque, 'result': ataque,
    }]
    page.locator('#importFile').set_input_files({
        'name': 'dados-negativos.json', 'mimeType': 'application/json',
        'buffer': json.dumps(payload).encode('utf-8'),
    })
    confirmar(page, 'SUBSTITUIR')
    navegar(page, 'timeline')
    assert page.locator('#timelineResults').locator('img, script, iframe, svg').count() == 0
    assert page.evaluate('window.__ataque ?? null') is None
    assert '<img src=x onerror=' in page.locator('#timelineResults').inner_text()
    assert page.evaluate('ReqSysPainelTeste.accepted()') == 0
