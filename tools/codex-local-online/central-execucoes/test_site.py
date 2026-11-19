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
        assert 'Sequência bloqueada' in page.locator('.modal [role="alert"]').inner_text()
        page.locator('#modal-close').click()
        # Negativo: impedir avanço fora de ordem.
        page.locator('#flow-list .step-card').nth(3).get_by_role('button',name='Detalhar').click()
        page.locator('#stage-state').select_option('documentada')
        page.locator('#field-evidence').fill('https://github.com/evidencia-externa/4')
        page.get_by_role('button',name='Registrar transição').click()
        assert 'Sequência bloqueada' in page.locator('.modal [role="alert"]').inner_text()
        page.locator('#modal-close').click()
        # Negativo: admissão precisa de campos de controle.
        page.locator('#flow-list .step-card').nth(1).get_by_role('button',name='Detalhar').click()
        page.locator('#stage-state').select_option('documentada')
        page.locator('#field-evidence').fill('https://github.com/evidencia-externa/2')
        page.get_by_role('button',name='Registrar transição').click()
        assert 'Campos indispensáveis' in page.locator('.modal [role="alert"]').inner_text()
        page.locator('#modal-close').click()
        # Controle negativo: mesma chave de idempotência impede duplicidade mesmo com correlação diferente.
        assert page.evaluate("""() => hasDuplicate(
          [{repo:'x/y',id:'1',issuePr:'#1',correlation:'corr-1',idempotency:'chave-x'}],
          {repo:'x/y',id:'2',issuePr:'#2',correlation:'corr-2',idempotency:'chave-x'})""") is True
        # Somente um prefixo contínuo pode compor o percentual documentado.
        assert page.evaluate("""() => {const r={...db.runs[0],stages:db.runs[0].stages.map((s,i)=>i===4 ? {status:'documentada',evidence:'etapa fora de ordem'} : s)};return prefixDocumented(r)===1&&progress(r)===8}""") is True
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
        # Evento duplicado em checkpoint com hash válido: importar deve ser operação atômica.
        fakeevent={'id':'evt-duplicado','when':'2026-11-19T00:00:00Z','action':'teste','runId':'','correlation':'','detail':'sem segredo'}
        envelope['dataset']['audit']=[fakeevent,fakeevent]
        envelope['digest_sha256']=hashlib.sha256(json.dumps(envelope['dataset'],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        duplicate=BASE/'_checkpoint_duplicate_test.json'
        duplicate.write_text(json.dumps(envelope,ensure_ascii=False))
        before=page.evaluate('JSON.stringify(db)')
        page.locator('#import-file').set_input_files(str(duplicate))
        page.wait_for_timeout(300)
        assert 'event_id duplicado' in page.locator('#toast').inner_text()
        assert page.evaluate('JSON.stringify(db)')==before
        duplicate.unlink()
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
        # Positivo de lógica local: todos os gates documentais satisfeitos.
        # Fixture não é prova externa, apenas verifica o comportamento da interface.
        flow_controls=page.evaluate("""() => {
          const fixture={...db.runs[0],todo:'REQ-TESTE',correlation:'corr-a',idempotency:'idem-a',
            expectedSha:'a'.repeat(40),confirmedSha:'a'.repeat(40),host:'HOST-A',recoveryHost:'HOST-B',
            lease:'lease-g1',recoveryLease:'lease-g2',worktree:'isolado',model:'qwen:teste',digest:'digest-do-modelo',
            builder:'finalizou teste local',validator:'testado separadamente',before:'antes',after:'depois',
            checkpoint:'ref-cas-teste',artifactHash:'b'.repeat(64),failure:'interrupcao do ensaio',
            tests:'positivo negativo regressao',cost:'COST_ZERO_CONFIRMED - fonte de teste',
            authorization:'autorizacao de ensaio local',realProof:'destino de teste',rollback:'reversao planejada',
            stages:STAGES.map((_,i)=>({status:i===11?'pendente':'documentada',evidence:'ref-controle-local-'+i})),
            evidences:['Teste positivo','Teste negativo','Replay idempotente','Efeito no destino real',
              'Artefato recuperável','Hash / leitura de bytes','Autorização específica'].map(kind=>({kind,reference:'teste',title:'teste'}))};
          const ok=flowGate(fixture,11);
          const noCost=flowGate({...fixture,cost:'COST_UNKNOWN_BLOCKED'},11);
          const wrongLease=flowGate({...fixture,recoveryLease:'lease-g1'},11);
          const wrongSha=flowGate({...fixture,confirmedSha:'c'.repeat(40)},11);
          const missingProof=flowGate({...fixture,evidences:[]},11);
          const missingPrevious=flowGate({...fixture,stages:fixture.stages.map((st,i)=>i===5?{status:'pendente',evidence:''}:st)},11);
          const staleFields={...fixture,worktree:'',stages:STAGES.map((_,i)=>({status:'documentada',evidence:'ref-stale-duravel-'+i}))};
          const forged={...staleFields,evidences:staleFields.evidences.map(e=>({...e,reference:'ref-teste-123456'})),id:'forjado-2',correlation:'corr-forjada',idempotency:'idem-forjada'};
          const imported=safeImportEnvelope({schema:'codex-local-central/v1',dataset:{runs:[forged],audit:[]}}, {runs:[],audit:[]});
          return {ok,noCost,wrongLease,wrongSha,missingProof,missingPrevious,
                  staleProgress:progress(staleFields),lateGate:flowGate(staleFields,8),imported};
        }""")
        assert flow_controls['ok']=='',flow_controls
        assert 'Custo não admitido' in flow_controls['noCost'],flow_controls
        assert 'lease' in flow_controls['wrongLease'].lower(),flow_controls
        assert 'SHA' in flow_controls['wrongSha'],flow_controls
        assert 'faltam referências' in flow_controls['missingProof'],flow_controls
        assert '11 etapas' in flow_controls['missingPrevious'],flow_controls
        # Regressão RED: campo necessário removido após documentação não pode preservar 100%.
        assert flow_controls['staleProgress'] == 17,flow_controls
        assert flow_controls['lateGate'],flow_controls
        assert 'etapa' in flow_controls['imported'].lower(),flow_controls
        # Retirar aprovação anterior deve tirar a etapa do percentual, preservando o histórico.
        page.locator('[data-page="flow"]').click()
        page.locator('#flow-list .step-card').first.get_by_role('button',name='Detalhar').click()
        page.locator('#stage-state').select_option('bloqueada')
        page.get_by_role('button',name='Registrar transição').click()
        assert page.evaluate('progress(db.runs[0])')==0
        assert page.evaluate('db.audit.at(-1).action').startswith('Transição')
        # Responsividade e ausência de dependências remotas
        page.locator('[data-page="dashboard"]').click()
        page.set_viewport_size({'width':390,'height':844})
        assert page.get_by_role('heading',name='Visão operacional').is_visible()
        assert not errors,errors
        assert not outgoing,outgoing
        # Cleanup tests; user-facing source remains
        dest.unlink()
        corrupt.unlink()
        browser.close()
        print('PASS: interface, deduplicação, sequência, gates positivos/negativos, SHA, custo, lease, rollback de progresso, importação atômica, mobile, sem requisições remotas')


if __name__=='__main__':
    run()

# Escopo: teste de interface local; nao certifica ambiente ReqSys nem host fisico.
