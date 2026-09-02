#!/usr/bin/env node
// Ferramenta interativa (roda localmente, uma vez, manualmente — NUNCA em CI).
// Abre um navegador real, você loga com a conta Microsoft de verdade (resolve
// MFA normalmente) e o script salva o estado da sessão do navegador (cookies +
// sessionStorage, onde o MSAL guarda o cache de tokens) em um arquivo local.
//
// Uso:
//   node scripts/setup-msal-storage-state.mjs
//
// Depois, para usar em CI sem guardar senha nenhuma:
//   base64 -w0 msal-storage-state.json | (cole como o secret
//   WSJF_MSAL_STORAGE_STATE_B64 no GitHub — Settings > Secrets > Actions)
//
// A sessão expira com o tempo (SSO/refresh token do tenant). Quando o teste
// E2E dedicado (wsjf-planner-excel-conexoes-live.spec.js) voltar a pular por
// falta de sessão válida, rode este script de novo e atualize o secret.

import { chromium } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const baseURL = process.env.E2E_BASE_URL || 'https://reqsys-app-dev.fly.dev'
const outputPath = process.env.MSAL_STORAGE_STATE_PATH || path.resolve(__dirname, '..', 'msal-storage-state.json')

async function main() {
  console.log(`Abrindo ${baseURL}/login em um navegador real...`)
  const browser = await chromium.launch({ headless: false })
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(`${baseURL}/login`)

  console.log('')
  console.log('>>> Clique em "Entrar com conta Microsoft" e complete o login')
  console.log('>>> (usuário/senha, MFA, "Continuar conectado?") normalmente.')
  console.log('>>> Este script espera até você voltar autenticado na aplicação.')
  console.log('')

  const appOrigin = new URL(baseURL).origin
  await page.waitForURL(
    (url) => url.origin === appOrigin && !url.pathname.startsWith('/login') && !url.pathname.startsWith('/auth/callback'),
    { timeout: 300_000 },
  )
  // Dá um tempo para o MSAL terminar de processar o retorno do redirect e
  // persistir o cache de tokens no sessionStorage antes de capturar o estado.
  await page.waitForTimeout(3000)

  await context.storageState({ path: outputPath })
  console.log(`Estado salvo em: ${outputPath}`)
  console.log('')
  console.log('Para usar em CI, gere o base64 e salve como secret WSJF_MSAL_STORAGE_STATE_B64:')
  console.log(`  base64 -w0 "${outputPath}"`)

  await browser.close()
}

if (process.env.CI) {
  console.error('Este script é interativo — não deve ser executado em CI.')
  process.exitCode = 1
} else {
  main().catch((err) => {
    console.error('Falha ao capturar o estado da sessão:', err)
    process.exitCode = 1
  })
}
