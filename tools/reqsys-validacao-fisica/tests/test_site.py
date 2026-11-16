import json
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
import pytest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def site_url():
    handler=partial(SimpleHTTPRequestHandler,directory=str(ROOT))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/index.html'
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture
def page(site_url):
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page()
        errs=[]
        page.on('pageerror',lambda e:errs.append(str(e)))
        page.goto(site_url)
        yield page
        assert not errs, f'Erros JS: {errs}'
        browser.close()

def navigate(page, target):
    page.locator(f'.navitem[data-view="{target}"]').click()

def approve(page, keyword='CONFIRMAR'):
    assert page.locator('#confirmDialog').is_visible()
    assert page.locator('#confirmOk').is_disabled()
    page.locator('#confirmInput').fill(keyword)
    page.locator('#confirmOk').click()

def test_pagina_inicial_e_limites(page):
    assert page.title()=='ReqSys · Validação física'
    assert 'Sem comprovação física' in page.locator('.notice').inner_text()
    assert page.evaluate('ReqSysPainelTeste.total()')==10
    assert page.evaluate('ReqSysPainelTeste.accepted()')==0
    assert page.locator('.host-card').count()==0
    assert page.locator('text=Não estimável').first.is_visible()
    assert page.locator('.navitem').count()==7
    assert page.evaluate('typeof fetch')=='function'
    assert 'fetch(' not in (Path(__file__).resolve().parents[1]/'app.js').read_text()

def test_fila_alteracao_exige_confirmacao_e_sha_positivo_negativo(page):
    navigate(page,'queue')
    assert page.locator('.data-table tbody tr').count()==5
    page.locator('[data-edit-task="P0-01"]').click()
    page.locator('#taskForm [name="confirmedSha"]').fill('123')
    page.locator('#taskForm button[type="submit"]').click()
    assert 'SHA deve ter 40 caracteres' in page.locator('.toast').inner_text()
    assert not page.locator('#confirmDialog').is_visible()
    sha='a'*40
    page.locator('#taskForm [name="confirmedSha"]').fill(sha)
    page.locator('#taskForm [name="nextAction"]').fill('Nova leitura somente leitura')
    page.locator('#taskForm button[type="submit"]').click()
    page.locator('#confirmDialog button[value="cancel"]').click()
    assert page.evaluate('ReqSysPainelTeste.state().tasks[0].nextAction')!='Nova leitura somente leitura'
    page.locator('#taskForm button[type="submit"]').click()
    approve(page)
    assert page.evaluate('ReqSysPainelTeste.state().tasks[0].confirmedSha')==sha
    assert page.evaluate('ReqSysPainelTeste.accepted()')==0
    page.reload()
    assert page.evaluate('ReqSysPainelTeste.state().tasks[0].nextAction')=='Nova leitura somente leitura'

def test_host_declarado_nao_fica_apto(page):
    navigate(page,'hosts')
    assert page.locator('.host-card').count()==3
    page.locator('[data-edit-host="DESKTOP-PDQK954"]').click()
    page.locator('#hostForm [name="physicalId"]').fill('Inventário revisado')
    page.locator('#hostForm [name="labels"]').fill('pc24x7,desktop-runtime,runtime-dev')
    page.locator('#hostForm [name="observedSha"]').fill('b'*40)
    for check in ['normal','session','validated','gateway','runner','network']:
        page.locator(f'#hostForm [name="{check}"]').check()
    page.locator('#hostForm [name="worktree"]').fill('worktree-isolado')
    page.locator('#hostForm [name="lease"]').fill('lease-teste')
    page.locator('#hostForm button[type="submit"]').click()
    approve(page)
    assert page.evaluate('ReqSysPainelTeste.hostReadyVerified()')==0
    assert page.locator('.host-card').first.locator('text=10/10').count()==1
    assert page.locator('.host-card').first.locator('text=Não comprovado').count()>=1

def test_evento_logs_e_checkpoint_nao_aumentam_aceite(page):
    navigate(page,'cycle')
    assert page.locator('.step-card').count()==10
    page.locator('[data-record-step="4"]').click()
    assert page.locator('#eventForm [name="step"]').input_value()=='4'
    page.locator('#eventForm [name="title"]').fill('Pickup real relatado')
    page.locator('#eventForm [name="kind"]').select_option('pickup')
    page.locator('#eventForm [name="sha"]').fill('invalido')
    page.locator('#eventForm button[type="submit"]').click()
    assert 'SHA de commit exige 40 caracteres' in page.locator('.toast').inner_text()
    assert page.evaluate('ReqSysPainelTeste.state().events.length')==0
    page.locator('#eventForm [name="sha"]').fill('c'*40)
    page.locator('#eventForm [name="command"]').fill('git status --short')
    page.locator('#eventForm [name="result"]').fill('Somente declaração local')
    page.locator('#eventForm [name="artifactHash"]').fill('d'*64)
    page.locator('#eventForm button[type="submit"]').click()
    approve(page)
    assert page.evaluate('ReqSysPainelTeste.state().events.length')==1
    assert page.evaluate('ReqSysPainelTeste.documents()')==1
    assert page.evaluate('ReqSysPainelTeste.accepted()')==0
    navigate(page,'timeline')
    assert 'Pickup real relatado' in page.locator('#timelineResults').inner_text()
    page.locator('#timelineFilter').select_option('falha')
    assert 'Nenhum registro' in page.locator('#timelineResults').inner_text()

def test_exportacao_local_e_importacao_com_confirmacao(page):
    navigate(page,'safety')
    with page.expect_download() as dl:
        page.locator('#exportAgain').click()
    d=dl.value
    assert d.suggested_filename=='reqsys-validacao-fisica.json'
    payload=json.loads(Path(d.path()).read_text())
    assert len(payload['tasks'])==5
    assert 'não autenticados' in payload['exportCaveat']
    with page.expect_download() as dl:
        page.locator('#exportMd').click()
    assert dl.value.suggested_filename.endswith('.md')

def test_sem_requisicoes_de_rede_e_responsivo(page):
    requests=[]
    page.on('request',lambda r:requests.append(r.url))
    page.set_viewport_size({'width':390,'height':844})
    navigate(page,'hosts')
    assert page.locator('.host-card').count()==3
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert all('127.0.0.1' in r for r in requests)
