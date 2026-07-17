import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const tokenFileUrl = new URL('../src/theme/design-tokens.json', import.meta.url)
const tokenFilePath = fileURLToPath(tokenFileUrl)

const requiredColorTokens = [
  'primary',
  'primaryDeep',
  'primarySoft',
  'accent',
  'accentDeep',
  'analytics',
  'analyticsDeep',
  'success',
  'warning',
  'critical',
  'background',
  'backgroundDeep',
  'surface',
  'surfaceElevated',
  'text',
  'muted',
  'border',
]

const requiredSemanticTokens = [
  'governance',
  'executiveHighlight',
  'informational',
  'healthy',
  'degraded',
  'criticalState',
]

const cssColorPattern = /^(#[0-9a-f]{6}|rgba?\([^)]+\))$/i

function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

async function main() {
  const rawContent = await readFile(tokenFilePath, 'utf8')
  const tokens = JSON.parse(rawContent)

  assert(tokens.$schema, 'Campo obrigatório ausente: $schema')
  assert(tokens.metadata?.version, 'Campo obrigatório ausente: metadata.version')
  assert(tokens.metadata?.governance === 'padrao-ouro', 'metadata.governance deve ser padrao-ouro')

  for (const tokenName of requiredColorTokens) {
    const value = tokens.colors?.[tokenName]
    assert(value, `Token de cor obrigatório ausente: colors.${tokenName}`)
    assert(cssColorPattern.test(value), `Cor inválida em colors.${tokenName}: ${value}`)
  }

  for (const semanticName of requiredSemanticTokens) {
    const referencedColor = tokens.semantic?.[semanticName]
    assert(referencedColor, `Token semântico obrigatório ausente: semantic.${semanticName}`)
    assert(
      Object.hasOwn(tokens.colors, referencedColor),
      `Referência semântica inválida: semantic.${semanticName} -> colors.${referencedColor}`,
    )
  }

  assert(tokens.radius?.card, 'Token obrigatório ausente: radius.card')
  assert(tokens.radius?.frame, 'Token obrigatório ausente: radius.frame')
  assert(tokens.typography?.fontFamily, 'Token obrigatório ausente: typography.fontFamily')

  console.log(
    `[design-tokens] contrato válido: ${tokens.metadata.name} v${tokens.metadata.version} (${requiredColorTokens.length} cores)`,
  )
}

main().catch((error) => {
  console.error(`[design-tokens] validação falhou: ${error.message}`)
  process.exitCode = 1
})
