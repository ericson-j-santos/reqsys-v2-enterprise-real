"""Testes reais no Chromium local, sem backend/rede ou publicação externa."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=Path(__file__).parent


def run():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(accept_downloads=True,viewport={'width':1365,'height':900})
        errors=[]
        outgoing=[]
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.on('request',lambda req:outgoing.append(req.url) if req.url.startswith('http') and '127.0.0.1' not in req.url else None)
        page.expose_function('__shaFromPython',lambda values:hashlib.sha256(bytes(values)).hexdigest())
        page.set_content((BASE/"index.html").read_text(),wait_until="load")
        # Ambiente de testes em about:blank não tem crypto.subtle (contexto inseguro).
        # A API do browser é substituída pelo SHA-256 real da biblioteca Python.
        page.evaluate("""() => Object.defineProperty(crypto,'subtle',{configurable:true,value:{digest: async (_,arrayBuffer) => {const hex=await window.__shaFromPython([...new Uint8Array(arrayBuffer)]);return Uint8Array.from(hex.match(/../g).map(x=>parseInt(x,16))).buffer}}})""")
        assert page.get_by_role('heading',name='Visão operacional').is_visible()
        assert page.locator('#metrics').inner_text().count('0')>=1
        assert not errors,errors
        # Formulário com campos reais existentes + correlação fictícia apenas para ensaio local
        page.locator('[data-action="new"]').first.click()
        page.locator('#field-objective').fill('Teste local isolado de integridade (não é demanda real)')
        page.locator('#field-reference').select_option('reqsys3126')
        page.locator('#field-correlation').fill('test-001-local')
        page.locator('#field-host').fill('HOST-A-TESTE')
        page.locator('#field-recoveryHost').fill('HOST-B-TESTE')
        page.get_by_role('button',name='Criar ficha local').click()
        assert page.evaluate('db.runs.length') == 1
        assert page.evaluate('db.runs[0].repo')=='ericson-j-santos/reqsys-v2-enterprise-real'
        # Teste negativo: bloqueio duplicado com a mesma chave canônica
        page.locator('[data-action="new"]').first.click()
        page.locator('#field-objective').fill('Cópia indevida')
        page.locator('#field-reference').select_option('reqsys3126')
        page.locator('#field-correlation').fill('test-001-local')
        page.get_by_role('button',name='Criar ficha local').click()
        assert 'Duplicidade' in page.locator('#run-error').inner_text()
        page.locator('#modal-close').click()
        # Teste negativo: possível segredo impede salvar
        page.locator('[data-action="new"]').first.click()
        page.locator('#field-objective').fill('Verificação segredo')
        page.locator('#field-reference').select_option('noteri42')
        page.locator('#field-correlation').fill('test-002-local')
        page.locator('#field-after').fill('Authorization: Bearer segredo')
        page.get_by_role('button',name='Criar ficha local').click()
        assert 'segredo ou dado pessoal' in page.locator('#run-error').inner_text().lower()
        page.locator('#modal-close').click()
        # Percorre etapas e registra checkpoint local, sem homologação
        page.locator('[data-page="flow"]').click()
        page.locator('#flow-list .step-card').first.get_by_role('button',name='Detalhar').click()
        page.locator('#stage-state').select_option('documentada')
        page.locator('#field-evidence').fill('https://github.com/exemplo/teste/1')
        page.get_by_role('button',name='Registrar transição').click()
        assert page.evaluate('progress(db.runs[0])')==8
        assert '1/12' in page.locator('#flow-progress').inner_text()
        # Falha segura se tentar encerrar sem gates completos
        page.locator('#flow-list .step-card').last.get_by_role('button',name='Detalhar').click()
        page.locator('#stage-state').select_option('documentada')
        page.locator('#field-evidence').fill('evidencia-de-encerramento-externo')
        page.get_by_role('button',name='Registrar transição').click()
        assert 'Encerramento bloqueado' in page.locator('.modal [role="alert"]').inner_text()
        page.locator('#modal-close').click()
        # Adiciona evidência com origem rastreável
        page.locator('[data-page="evidences"]').click()
        page.get_by_role('button',name='+ Nova evidência').click()
        page.locator('#field-title').fill('Saída de teste positivo sem dados pessoais')
        page.locator('#field-reference').fill('https://github.com/exemplo/acao/123')
        page.locator('#field-description').fill('Simulação local, não confirma efeito real')
        page.get_by_role('button',name='Anexar referência local').click()
        assert page.evaluate('db.runs[0].evidences.length')==1
        # Exporta bytes reais do navegador e verifica SHA com importação sem duplicação
        with page.expect_download() as info:
            page.locator('[data-page="dashboard"]').click()
            page.get_by_role('button',name='Exportar checkpoint').click()
        download=info.value
        dest=BASE/'_checkpoint_test.json'
        download.save_as(dest)
        envelope=json.loads(dest.read_text())
        assert envelope['schema']=='codex-local-central/v1'
        assert len(envelope['digest_sha256'])==64
        old_count=page.evaluate('db.runs.length')
        page.locator('#import-file').set_input_files(str(dest))
        page.wait_for_timeout(300)
        assert page.evaluate('db.runs.length')==old_count
        # Controle negativo: hash alterado deve ser rejeitado sem perda
        corrupt=BASE/'_checkpoint_corrupt_test.json'
        envelope['digest_sha256']='0'*64
        corrupt.write_text(json.dumps(envelope))
        page.locator('#import-file').set_input_files(str(corrupt))
        page.wait_for_timeout(300)
        assert 'SHA-256 divergente' in page.locator('#toast').inner_text()
        assert page.evaluate('db.runs.length')==old_count
        # Controles negativos puros: SHA inválido, divergente e mesmo host físico
        gate=page.evaluate('''() => {
          const base={...db.runs[0],expectedSha:'a'.repeat(40),confirmedSha:'b'.repeat(40),classification:'Fato comprovado (informado)'};
          const shaError=validateRun(base,[],base.id);
          const invalidSha=validateRun({...base,expectedSha:'xyz'},[],base.id);
          const sameHost=validateRun({...db.runs[0],host:'HOST-A-TESTE',recoveryHost:'HOST-A-TESTE',stages:db.runs[0].stages.map((x,i)=>i===6?{status:'documentada',evidence:'readback id externo'}:x)},[],db.runs[0].id);
          return [shaError,invalidSha,sameHost];
        }''')
        assert 'divergente' in gate[0].lower(), gate
        assert '40 caracteres' in gate[1], gate
        assert 'segundo host' in gate[2].lower(), gate
        # Responsividade e ausência de dependências remotas
        page.set_viewport_size({'width':390,'height':844})
        assert page.get_by_role('heading',name='Visão operacional').is_visible()
        assert not errors,errors
        assert not outgoing,outgoing
        # Cleanup tests; user-facing source remains
        dest.unlink()
        corrupt.unlink()
        browser.close()
        print('PASS: abertura, inclusão, vínculo, antidupe, antissegredo, progressão, encerramento bloqueado, evidência, exportação SHA, replay de importação, corrupção, mobile, sem requisições remotas')


if __name__=='__main__':
    run()

# Escopo: teste de interface local; nao certifica ambiente ReqSys nem host fisico.
