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

const requiredTypographyScaleTokens = ['xs', 'sm', 'md', 'base', 'lg', 'xl', '2xl', 'display']
const requiredSpacingTokens = ['xs', 'sm', 'md', 'lg', 'xl', '2xl', '3xl']
const requiredZIndexTokens = ['routeFeedback', 'toast', 'connectivityAlert', 'skipLink', 'tooltip']

const cssColorPattern = /^(#[0-9a-f]{6}|rgba?\([^)]+\))$/i
const cssSizePattern = /^-?[0-9.]+(px|rem|em)$/

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

  for (const scaleName of requiredTypographyScaleTokens) {
    const value = tokens.typography?.scale?.[scaleName]
    assert(value, `Token de tipografia obrigatório ausente: typography.scale.${scaleName}`)
    assert(cssSizePattern.test(value), `Tamanho inválido em typography.scale.${scaleName}: ${value}`)
  }

  for (const spacingName of requiredSpacingTokens) {
    const value = tokens.spacing?.[spacingName]
    assert(value, `Token de espaçamento obrigatório ausente: spacing.${spacingName}`)
    assert(cssSizePattern.test(value), `Tamanho inválido em spacing.${spacingName}: ${value}`)
  }

  for (const zIndexName of requiredZIndexTokens) {
    const value = tokens.zIndex?.[zIndexName]
    assert(Number.isInteger(value), `Token de z-index obrigatório ausente ou inválido: zIndex.${zIndexName}`)
  }
  assert(
    tokens.zIndex.routeFeedback < tokens.zIndex.toast &&
      tokens.zIndex.toast < tokens.zIndex.connectivityAlert &&
      tokens.zIndex.connectivityAlert < tokens.zIndex.skipLink &&
      tokens.zIndex.skipLink < tokens.zIndex.tooltip,
    'Escala zIndex deve seguir a ordem: routeFeedback < toast < connectivityAlert < skipLink < tooltip ' +
      '(tooltip precisa ficar acima de tudo: Vuetify fixa VTooltip em zIndex 2000 sem participar do stack global, ' +
      'então qualquer overlay do app acima disso o cobre)',
  )

  assert(tokens.table?.density, 'Token obrigatório ausente: table.density')
  assert(cssSizePattern.test(tokens.table?.rowFontSize ?? ''), `Tamanho inválido em table.rowFontSize: ${tokens.table?.rowFontSize}`)

  console.log(
    `[design-tokens] contrato válido: ${tokens.metadata.name} v${tokens.metadata.version} (${requiredColorTokens.length} cores)`,
  )
}

main().catch((error) => {
  console.error(`[design-tokens] validação falhou: ${error.message}`)
  process.exitCode = 1
})
