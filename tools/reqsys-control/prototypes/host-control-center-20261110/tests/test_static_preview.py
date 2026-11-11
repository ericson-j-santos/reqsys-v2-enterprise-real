"""Teste de interface estática: não equivale ao E2E físico ou à validação de CI."""
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = Path(__file__).resolve().parents[1] / 'index.html'


def test_preview():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1300, 'height': 800})
        errors = []
        external = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: external.append(request.url)
                if request.url.startswith('http') else None)
        page.set_content(HTML.read_text(encoding='utf-8'))
        assert page.locator('#stat-tasks').inner_text() == '4'
        assert page.locator('#dispatch-blocked').is_disabled()
        assert page.locator('#execute-intent').is_disabled()
        page.locator('a[data-page="hosts"]').click()
        assert page.locator('.host-card').count() == 4
        assert page.get_by_text('ready_for_work = false').count() == 4
        page.locator('a[data-page="fluxo"]').click()
        page.locator('#evaluate-flow').click()
        assert 'Bloqueado' in page.locator('#flow-decision').inner_text()
        assert page.locator('#dispatch-blocked').is_disabled()
        page.locator('a[data-page="automacoes"]').click()
        page.get_by_role('button', name='Gerar prévia →').first.click()
        assert '"mutation_allowed": false' in page.locator('#automation-output').inner_text()
        assert not errors, errors
        assert not external, external
        browser.close()


if __name__ == '__main__':
    test_preview()
    print('PASS: UI, quatro hosts bloqueados, fluxo fail-closed e zero tráfego externo.')
