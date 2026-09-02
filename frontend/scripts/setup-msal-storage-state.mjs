#!/usr/bin/env node
// Ferramenta interativa local para capturar uma sessao Microsoft real.
// NUNCA deve rodar em CI e nunca captura senha: o login e o MFA acontecem
// diretamente no navegador da Microsoft.
//
// Importante: Playwright storageState NAO persiste sessionStorage. Como o
// ReqSys configura o MSAL com cacheLocation=sessionStorage, este script salva
// um envelope proprio contendo:
//   - storageState nativo do Playwright (cookies/localStorage);
//   - sessionStorage do origin do ReqSys (cache MSAL).
//
// Uso (a partir de frontend/):
//   npm run setup:msal-state
//
// O arquivo gerado e sensivel e esta ignorado pelo Git. Cadastre somente seu
// base64 como secret WSJF_MSAL_STORAGE_STATE_B64 no GitHub Actions.

import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const baseURL = process.env.E2E_BASE_URL || 'https://reqsys-app-dev.fly.dev'
const outputPath = process.env.MSAL_STORAGE_STATE_PATH || path.resolve(__dirname, '..', 'msal-storage-state.json')

function hasMsalCache(entries) {
  return entries.some(([name]) => String(name).toLowerCase().includes('msal'))
}

async function main() {
  console.log(`Abrindo ${baseURL}/login em um navegador real...`)
  const browser = await chromium.launch({ headless: false })

  try {
    const context = await browser.newContext()
    const page = await context.newPage()
    await page.goto(`${baseURL}/login`)

    console.log('')
    console.log('>>> Clique em "Entrar com conta Microsoft" e complete o login.')
    console.log('>>> Conclua usuario/senha, MFA e eventuais confirmacoes normalmente.')
    console.log('>>> O script espera o retorno autenticado ao ReqSys.')
    console.log('')

    const appOrigin = new URL(baseURL).origin
    await page.waitForURL(
      (url) => url.origin === appOrigin && !url.pathname.startsWith('/login') && !url.pathname.startsWith('/auth/callback'),
      { timeout: 300_000 },
    )

    // Aguarda o redirect MSAL terminar e o cache ser persistido antes da coleta.
    await page.waitForTimeout(3000)

    const storageState = await context.storageState()
    const sessionStorageEntries = await page.evaluate(() => Object.entries(window.sessionStorage))

    if (!hasMsalCache(sessionStorageEntries)) {
      throw new Error('Login retornou ao ReqSys, mas nenhum cache MSAL foi encontrado no sessionStorage. A sessao nao sera exportada.')
    }

    const authBundle = {
      schemaVersion: 1,
      origin: appOrigin,
      capturedAt: new Date().toISOString(),
      storageState,
      sessionStorage: sessionStorageEntries.map(([name, value]) => ({ name, value })),
    }

    await fs.writeFile(outputPath, `${JSON.stringify(authBundle, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 })
    await fs.chmod(outputPath, 0o600).catch(() => {})

    console.log(`Estado MSAL salvo em: ${outputPath}`)
    console.log(`Entradas de sessionStorage capturadas: ${sessionStorageEntries.length}`)
    console.log('')
    console.log('Cadastre o conteudo em base64 no secret WSJF_MSAL_STORAGE_STATE_B64.')
    console.log('Linux/macOS:')
    console.log(`  base64 < "${outputPath}" | tr -d '\\n'`)
    console.log('PowerShell:')
    console.log(`  [Convert]::ToBase64String([IO.File]::ReadAllBytes("${outputPath}"))`)
  } finally {
    await browser.close()
  }
}

if (process.env.CI) {
  console.error('Este script e interativo e nao deve ser executado em CI.')
  process.exitCode = 1
} else {
  main().catch((err) => {
    console.error('Falha ao capturar o estado da sessao:', err instanceof Error ? err.message : err)
    process.exitCode = 1
  })
}
