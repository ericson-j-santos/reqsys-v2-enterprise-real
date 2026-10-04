#!/usr/bin/env node
// Gerenciador do estado MSAL capturado por setup-msal-storage-state.mjs.
//
// O refresh token de um app SPA tem vida fixa de 24h (AADSTS700084) e nao
// pode ser renovado além disso -- so um novo login interativo resolve. Esse
// limite so costumava aparecer como erro tardio (ex.: 'invalid_grant' no
// meio de um script que dependia da sessao capturada). Este script le o
// mesmo arquivo e responde a pergunta direto: a sessao ainda serve, ou
// preciso rodar `npm run setup:msal-state` de novo?
//
// Uso (a partir de frontend/):
//   npm run check:msal-state            # texto legivel, sai 0/1/2
//   npm run check:msal-state -- --json  # saida em JSON para scripts

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const AVISO_HORAS = 2

export function formatarDuracao(segundos) {
  const abs = Math.abs(segundos)
  const horas = Math.floor(abs / 3600)
  const minutos = Math.floor((abs % 3600) / 60)
  if (horas === 0) return `${minutos}min`
  return `${horas}h${String(minutos).padStart(2, '0')}min`
}

export function decodificarJwtPayload(jwt) {
  try {
    const [, payloadB64] = jwt.split('.')
    const json = Buffer.from(payloadB64, 'base64url').toString('utf8')
    return JSON.parse(json)
  } catch {
    return null
  }
}

export function avaliarEstado(statePath) {
  if (!fs.existsSync(statePath)) {
    return { status: 'ausente', statePath, mensagem: `Nenhum estado MSAL encontrado em ${statePath}.` }
  }

  const bundle = JSON.parse(fs.readFileSync(statePath, 'utf8'))
  const entries = Array.isArray(bundle.sessionStorage) ? bundle.sessionStorage : []

  const refreshEntry = entries.find((e) => {
    try {
      return JSON.parse(e.value).credentialType === 'RefreshToken'
    } catch {
      return false
    }
  })
  if (!refreshEntry) {
    return { status: 'invalido', statePath, mensagem: 'Arquivo existe, mas nao contem um RefreshToken do MSAL (cache incompleto ou de outro schema).' }
  }

  const refresh = JSON.parse(refreshEntry.value)
  const expiresOnEpoch = Number(refresh.expiresOn)
  if (!Number.isFinite(expiresOnEpoch)) {
    return { status: 'invalido', statePath, mensagem: 'RefreshToken encontrado, mas sem "expiresOn" legivel.' }
  }

  const idEntry = entries.find((e) => {
    try {
      return JSON.parse(e.value).credentialType === 'IdToken'
    } catch {
      return false
    }
  })
  let conta = null
  if (idEntry) {
    const idToken = JSON.parse(idEntry.value)
    const claims = idToken.secret ? decodificarJwtPayload(idToken.secret) : null
    conta = claims?.preferred_username || claims?.upn || null
  }

  const agora = Date.now() / 1000
  const restanteSegundos = expiresOnEpoch - agora
  const capturedAt = bundle.capturedAt || null

  if (restanteSegundos <= 0) {
    return {
      status: 'expirado',
      statePath,
      conta,
      capturedAt,
      expiraEm: new Date(expiresOnEpoch * 1000).toISOString(),
      mensagem: `Sessao expirada ha ${formatarDuracao(restanteSegundos)}. Rode "npm run setup:msal-state" para capturar uma nova.`,
    }
  }

  if (restanteSegundos <= AVISO_HORAS * 3600) {
    return {
      status: 'expirando',
      statePath,
      conta,
      capturedAt,
      expiraEm: new Date(expiresOnEpoch * 1000).toISOString(),
      restanteSegundos: Math.round(restanteSegundos),
      mensagem: `Sessao ainda valida, mas expira em ${formatarDuracao(restanteSegundos)}. Considere recapturar em breve (rodar "npm run setup:msal-state").`,
    }
  }

  return {
    status: 'valido',
    statePath,
    conta,
    capturedAt,
    expiraEm: new Date(expiresOnEpoch * 1000).toISOString(),
    restanteSegundos: Math.round(restanteSegundos),
    mensagem: `Sessao valida por mais ${formatarDuracao(restanteSegundos)}.`,
  }
}

export const EXIT_CODES = { valido: 0, expirando: 0, expirado: 1, invalido: 2, ausente: 2 }

function main() {
  const statePath = process.env.MSAL_STORAGE_STATE_PATH || path.resolve(__dirname, '..', 'msal-storage-state.json')
  const asJson = process.argv.includes('--json')
  const resultado = avaliarEstado(statePath)

  if (asJson) {
    console.log(JSON.stringify(resultado, null, 2))
  } else {
    const rotulos = {
      valido: '✓ VALIDO',
      expirando: '! EXPIRANDO',
      expirado: '✗ EXPIRADO',
      invalido: '✗ INVALIDO',
      ausente: '✗ AUSENTE',
    }
    console.log(`Estado MSAL: ${statePath}`)
    console.log(rotulos[resultado.status])
    if (resultado.conta) console.log(`Conta: ${resultado.conta}`)
    if (resultado.capturedAt) console.log(`Capturado em: ${resultado.capturedAt}`)
    if (resultado.expiraEm) console.log(`Expira em (absoluto): ${resultado.expiraEm}`)
    console.log(resultado.mensagem)
  }

  process.exitCode = EXIT_CODES[resultado.status]
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main()
}
