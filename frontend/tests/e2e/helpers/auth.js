const { expect } = require('@playwright/test')

const EMAIL_PADRAO = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
const SENHA_PADRAO = 'admin123'

async function preencherPrimeiroDisponivel(candidatos, valor) {
  let ultimoErro = null

  for (const candidato of candidatos) {
    try {
      await candidato.first().fill(valor, { timeout: 4000 })
      return
    } catch (erro) {
      ultimoErro = erro
    }
  }

  throw ultimoErro || new Error('Nenhum campo disponível para preenchimento')
}

async function clicarPrimeiroDisponivel(candidatos) {
  let ultimoErro = null

  for (const candidato of candidatos) {
    try {
      await candidato.first().click({ timeout: 4000 })
      return
    } catch (erro) {
      ultimoErro = erro
    }
  }

  throw ultimoErro || new Error('Nenhum botão disponível para clique')
}

async function preencherFormularioLogin(page, email, senha) {
  await preencherPrimeiroDisponivel([
    page.getByLabel(/e-?mail/i),
    page.locator('input[type="email"]'),
    page.locator('input[name="email"]'),
    page.locator('input[autocomplete="username"]'),
    page.getByPlaceholder(/e-?mail/i),
  ], email)

  await preencherPrimeiroDisponivel([
    page.getByRole('textbox', { name: /^Senha$/i }),
    page.getByLabel(/^Senha$/i),
    page.locator('input[type="password"]'),
    page.locator('input[name="senha"]'),
    page.locator('input[autocomplete="current-password"]'),
  ], senha)

  await clicarPrimeiroDisponivel([
    page.getByRole('button', { name: /^Entrar$/i }),
    page.getByRole('button', { name: /entrar/i }),
  ])
}

async function login(page, options = {}) {
  const {
    email = EMAIL_PADRAO,
    senha = SENHA_PADRAO,
    expectedUrl = /\/$/,
    waitUntil = 'domcontentloaded',
  } = options

  await page.goto('/login', { waitUntil })
  await preencherFormularioLogin(page, email, senha)
  await expect(page).toHaveURL(expectedUrl, { timeout: 15000 })
}

module.exports = {
  EMAIL_PADRAO,
  SENHA_PADRAO,
  login,
  preencherFormularioLogin,
}
