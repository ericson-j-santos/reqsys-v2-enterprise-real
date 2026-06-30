const { expect } = require('@playwright/test')

async function instalarStubNavegacaoAmbiente(page) {
  await page.addInitScript(() => {
    window.__reqsysNavegacaoAmbiente = []
    window.__reqsysInterceptarNavegacaoAmbiente = (url) => {
      window.__reqsysNavegacaoAmbiente.push(String(url))
    }
  })
}

async function lerNavegacoesAmbiente(page) {
  return page.evaluate(() => window.__reqsysNavegacaoAmbiente || [])
}

async function abrirMenuAmbienteDrawer(page) {
  await page.getByTestId('ambiente-navigator-drawer').click()
  await expect(page.getByTestId('ambiente-navigator-menu')).toBeVisible()
}

async function selecionarAmbienteNoMenu(page, shortId) {
  await page.getByTestId(`ambiente-opcao-${shortId}`).click()
}

module.exports = {
  instalarStubNavegacaoAmbiente,
  lerNavegacoesAmbiente,
  abrirMenuAmbienteDrawer,
  selecionarAmbienteNoMenu,
}
