import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { avaliarEstado, decodificarJwtPayload, formatarDuracao } from './check-msal-state.mjs'

// mkdtemp (nao um nome de arquivo montado a mao em os.tmpdir()) e o jeito
// seguro de criar arquivos temporarios em Node: o diretorio recebe um sufixo
// aleatorio verificado pelo proprio SO, sem a corrida/previsibilidade que um
// nome montado com Date.now()/Math.random() teria (CWE-377, pego pelo
// CodeQL na primeira versao deste arquivo).
const dirTemp = fs.mkdtempSync(path.join(os.tmpdir(), 'msal-state-teste-'))
test.after(() => fs.rmSync(dirTemp, { recursive: true, force: true }))
let proximoId = 0

function caminhoTemp(sufixo) {
  proximoId += 1
  return path.join(dirTemp, `${proximoId}-${sufixo}`)
}

function escreverEstado(overrides = {}) {
  const arquivo = caminhoTemp('estado.json')
  const bundle = {
    schemaVersion: 1,
    origin: 'https://reqsys-app-dev.fly.dev',
    capturedAt: '2026-09-04T10:00:00.000Z',
    storageState: { cookies: [], origins: [] },
    sessionStorage: [
      { name: 'msal.refreshtoken', value: JSON.stringify({ credentialType: 'RefreshToken', expiresOn: String(overrides.expiresOn), secret: 'fake' }) },
    ],
    ...overrides.bundleOverrides,
  }
  fs.writeFileSync(arquivo, JSON.stringify(bundle))
  return arquivo
}

test('formatarDuracao mostra so minutos quando menos de 1h', () => {
  assert.equal(formatarDuracao(59 * 60), '59min')
})

test('formatarDuracao mostra horas e minutos com padding', () => {
  assert.equal(formatarDuracao(3 * 3600 + 5 * 60), '3h05min')
})

test('decodificarJwtPayload le o payload sem validar assinatura', () => {
  const payload = { preferred_username: 'usuario@teste.com' }
  const jwt = `x.${Buffer.from(JSON.stringify(payload)).toString('base64url')}.y`
  assert.deepEqual(decodificarJwtPayload(jwt), payload)
})

test('decodificarJwtPayload devolve null para entrada invalida', () => {
  assert.equal(decodificarJwtPayload('nao-e-um-jwt'), null)
})

test('avaliarEstado: arquivo ausente', () => {
  const resultado = avaliarEstado(path.join(os.tmpdir(), 'nao-existe-de-verdade.json'))
  assert.equal(resultado.status, 'ausente')
})

test('avaliarEstado: sessao valida por mais de 2h', () => {
  const arquivo = escreverEstado({ expiresOn: Math.floor(Date.now() / 1000) + 5 * 3600 })
  try {
    const resultado = avaliarEstado(arquivo)
    assert.equal(resultado.status, 'valido')
  } finally {
    fs.unlinkSync(arquivo)
  }
})

test('avaliarEstado: sessao expirando em menos de 2h vira aviso, nao erro', () => {
  const arquivo = escreverEstado({ expiresOn: Math.floor(Date.now() / 1000) + 3600 })
  try {
    const resultado = avaliarEstado(arquivo)
    assert.equal(resultado.status, 'expirando')
  } finally {
    fs.unlinkSync(arquivo)
  }
})

test('avaliarEstado: sessao expirada', () => {
  const arquivo = escreverEstado({ expiresOn: Math.floor(Date.now() / 1000) - 3600 })
  try {
    const resultado = avaliarEstado(arquivo)
    assert.equal(resultado.status, 'expirado')
    assert.match(resultado.mensagem, /setup:msal-state/)
  } finally {
    fs.unlinkSync(arquivo)
  }
})

test('avaliarEstado: arquivo sem RefreshToken no cache fica invalido', () => {
  const arquivo = caminhoTemp('sem-refresh.json')
  fs.writeFileSync(arquivo, JSON.stringify({
    schemaVersion: 1,
    sessionStorage: [{ name: 'msal.version', value: '"3.0.0"' }],
  }))
  try {
    const resultado = avaliarEstado(arquivo)
    assert.equal(resultado.status, 'invalido')
  } finally {
    fs.unlinkSync(arquivo)
  }
})

test('avaliarEstado: extrai a conta do IdToken quando presente', () => {
  const claims = { preferred_username: 'ericson@tieri659.onmicrosoft.com' }
  const idJwt = `x.${Buffer.from(JSON.stringify(claims)).toString('base64url')}.y`
  const arquivo = caminhoTemp('conta.json')
  fs.writeFileSync(arquivo, JSON.stringify({
    schemaVersion: 1,
    capturedAt: '2026-09-04T10:00:00.000Z',
    sessionStorage: [
      { name: 'msal.refreshtoken', value: JSON.stringify({ credentialType: 'RefreshToken', expiresOn: String(Math.floor(Date.now() / 1000) + 5 * 3600) }) },
      { name: 'msal.idtoken', value: JSON.stringify({ credentialType: 'IdToken', secret: idJwt }) },
    ],
  }))
  try {
    const resultado = avaliarEstado(arquivo)
    assert.equal(resultado.conta, 'ericson@tieri659.onmicrosoft.com')
  } finally {
    fs.unlinkSync(arquivo)
  }
})
