"""Testes de contrato do novo leitor GitHub: rede simulada no navegador, sem mutações externas."""
from __future__ import annotations
from pathlib import Path
import json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

BASE=Path(__file__).parent
REPOS=['ericson-j-santos/reqsys-v2-enterprise-real','ericson-j-santos/noteri-runtime','ericson-j-santos/desktop-pc24x7-runtime','ericson-j-santos/chatgpt-operational-rules']
RUN_ID='40150560475'
SHA='a'*40


def main():
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  page=browser.new_page(viewport={'width':1280,'height':900})
  errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  def mock(route):
   req=route.request
   u=urlparse(req.url)
   requests.append((req.method,req.url,req.headers))
   assert req.method=='GET',req.method
   assert u.netloc=='api.github.com',req.url
   assert 'authorization' not in req.headers,req.headers
   assert 'cookie' not in req.headers,req.headers
   path=u.path
   assert path.startswith('/repos/ericson-j-santos/'),path
   repo=next((r for r in REPOS if path.startswith('/repos/'+r+'/')),None)
   assert repo is not None,path
   tail=path.split('/repos/'+repo+'/')[1]
   if tail=='branches/main': data={'name':'main','commit':{'sha':SHA},'protected':True}
   elif tail in ('issues/3126','issues/42'):
    ident=int(tail.split('/')[1]);data={'number':ident,'html_url':'https://github.com/'+repo+'/issues/'+str(ident),'state':'open','title':'Teste público da issue','updated_at':'2026-11-19T01:00:00Z'}
   elif tail=='actions/runs/'+RUN_ID:
    data={'id':int(RUN_ID),'repository':{'full_name':repo},'html_url':'https://github.com/'+repo+'/actions/runs/'+RUN_ID,'head_sha':SHA,'status':'completed','conclusion':'success','run_attempt':1,'event':'workflow_dispatch','created_at':'2026-11-19T01:00:00Z','updated_at':'2026-11-19T01:02:00Z'}
   elif tail=='actions/runs/'+RUN_ID+'/jobs': data={'total_count':1,'jobs':[{'name':'Builder real — exemplo de teste','runner_name':'Desktop-TESTE','status':'completed','conclusion':'success'}]}
   elif tail=='actions/runs/'+RUN_ID+'/artifacts': data={'total_count':1,'artifacts':[{'name':'checkpoint-TESTE','id':12345,'expired':False,'digest':'sha256:'+'b'*64}]}
   else: raise AssertionError('Rota GET não esperada: '+req.url)
   route.fulfill(status=200,body=json.dumps(data),content_type='application/json',headers={'access-control-allow-origin':'*'})
  page.route('https://api.github.com/**',mock)
  page.set_content((BASE/'index.html').read_text(),wait_until='load')
  assert page.locator('#sources-title').count()==1
  assert requests==[],requests
  page.locator('[data-page="sources"]').click()
  assert requests==[],requests
  page.locator('#sources-read').click()
  page.wait_for_function("() => !document.querySelector('#sources-read').disabled")
  assert len(requests)==6,len(requests)
  assert 'Aberta' in page.locator('#sources-results').inner_text()
  assert SHA in page.locator('#sources-results').inner_text()
  assert 'não SHA de execução física' in page.locator('#sources-results').inner_text()
  assert page.evaluate('db.runs.length')==0
  # No run ID: bloquear sem qualquer nova requisição.
  page.locator('[data-page="runs"]').click()
  page.locator('#page-runs [data-action="new"]').click()
  page.locator('#field-objective').fill('Inspeção local - teste de run')
  page.locator('#field-reference').select_option('reqsys3126')
  page.locator('#field-correlation').fill('teste-contrato-sources')
  page.get_by_role('button',name='Criar ficha local').click()
  assert page.evaluate('db.runs.length')==1
  page.locator('[data-page="sources"]').click()
  prior=len(requests)
  page.locator('#source-run-read').click()
  assert 'run_id ausente' in page.locator('#source-run-result').inner_text()
  assert len(requests)==prior
  # preenchimento manual de run conhecido somente para testar GET
  page.evaluate("([runId,sha]) => {db.runs[0].runId=runId;db.runs[0].expectedSha=sha;render()}",[RUN_ID,SHA])
  page.locator('#source-run-read').click()
  page.wait_for_function("() => !document.querySelector('#source-run-read').disabled")
  assert len(requests)==prior+3,requests
  txt=page.locator('#source-run-result').inner_text()
  assert 'Run '+RUN_ID in txt,txt
  assert 'Builder real — exemplo de teste' in txt
  assert 'não comprovam conteúdo recuperável' in txt.lower()
  assert 'Não verificado por esta API' in txt
  assert page.evaluate('db.runs[0].confirmedSha')=='' # Proíbe preenchimento automático
  assert page.evaluate('db.audit.length')==1 # Leitura não cria prova local
  # Negativo SHA divergente mantém bloqueio e não altera a ficha.
  page.evaluate("() => {db.runs[0].expectedSha='b'.repeat(40);render()}")
  page.locator('#source-run-read').click()
  page.wait_for_function("() => !document.querySelector('#source-run-read').disabled")
  assert 'SHA divergente' in page.locator('#source-run-result').inner_text()
  assert page.evaluate('db.runs[0].confirmedSha')==''
  # Negativo origem não permitida, sem chamada de rede.
  prev=len(requests)
  page.evaluate("() => {db.runs[0].repo='evil-org/repo';render()}")
  page.locator('#source-run-read').click()
  assert 'Repositório não permitido' in page.locator('#source-run-result').inner_text()
  assert len(requests)==prev
  assert not errors,errors
  # Falha de rede API (429/403) deve deixar estado bloqueado
  page.unroute('https://api.github.com/**',mock)
  page.route('https://api.github.com/**',lambda route:route.fulfill(status=403,body='{"message":"API rate limit"}',content_type='application/json',headers={'access-control-allow-origin':'*'}))
  page.locator('#sources-read').click()
  page.wait_for_function("() => !document.querySelector('#sources-read').disabled")
  assert 'Leitura indisponível' in page.locator('#sources-results').inner_text()
  assert 'Limite de API pública' in page.locator('#sources-results').inner_text()
  assert not errors,errors
  browser.close()
  print('PASS: GET público explícito, seis vínculos, issues/main, run/jobs/artifacts, SHA, não-mutação, CORS simulado, bloqueios e rate limit')

if __name__=='__main__': main()

# Escopo: teste de interface local; nao certifica ambiente ReqSys nem host fisico.
