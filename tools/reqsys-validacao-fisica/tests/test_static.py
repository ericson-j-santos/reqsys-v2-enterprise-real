from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text()
JS=(ROOT/'app.js').read_text()
CSS=(ROOT/'styles.css').read_text()

def test_arquivos_presentes_e_locais():
    for name in ['index.html','app.js','styles.css','README.md']:
        assert (ROOT/name).is_file()
    assert 'https://' not in HTML
    assert '<script defer src="./app.js"></script>' in HTML

def test_sem_execucao_remota_ou_automatica():
    for blocked in ['fetch(', 'XMLHttpRequest(', 'WebSocket(', 'EventSource(', 'eval(', 'child_process', 'docker run']:
        assert blocked not in JS

def test_inputs_escapados_na_interface():
    assert 'const esc=' in JS
    assert 'esc(e.title)' in JS
    assert 'esc(t.title)' in JS
    assert 'esc(h.id)' in JS

def test_controle_consentimento_antes_do_registro():
    assert "if(!await ask(title,msg))return false" in JS
    assert 'btn.disabled=true' in JS
    assert "'SUBSTITUIR'" in JS

def test_aceite_fisico_nao_inferido():
    assert 'const confirmed=()=>0' in JS
    assert 'const ready=(h)' in JS
    assert "hostReadyVerified:()=>0" in JS
    assert '0 / 10' in JS

def test_ptbr_acessibilidade_responsividade():
    soup=BeautifulSoup(HTML,'html.parser')
    assert soup.html['lang']=='pt-BR'
    assert soup.select_one('a.skip')
    assert soup.select_one('main#conteudo')
    assert soup.select_one('dialog#confirmDialog')
    assert 'prefers-reduced-motion' in CSS
    assert '@media(max-width:760px)' in CSS

def test_lista_estagios_e_hosts_definida():
    assert JS.count("['Preflight somente leitura'")==1
    for h in ['DESKTOP-PDQK954','DESKTOP-RP23OGS','Noteri']:
        assert h in JS
    assert len(re.findall(r'^\[\'[^\']+\',\'[^\']+\'\]', JS,flags=re.M)) >= 9

def test_construcao_dom_seguranca_sem_html_ativo():
    assert not re.search(r'\.inner' + r'HTML\s*=', JS)
    assert 'new DOMParser().parseFromString' in JS
    assert 'SAFE_TAGS' in JS and 'SAFE_ATTRS' in JS
    assert 'node.setAttribute(nome,attr.value)' in JS
    assert 'renderSeguro(el(\'#screen\')' in JS
    assert 'renderSeguro(el(\'#timelineResults\')' in JS
