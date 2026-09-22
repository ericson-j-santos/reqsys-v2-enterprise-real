import designTokens from './design-tokens.json'

/**
 * Tokens e tema Vuetify alinhados ao contrato canônico do DSC ReqSys.
 *
 * `design-tokens.json` é a fonte única de verdade. Este adaptador preserva os
 * nomes históricos usados pelos componentes e pelo tema `figmaPadraoOuro`,
 * evitando duplicação e drift entre Figma, documentação e runtime.
 */
const { colors, radius, typography, spacing, zIndex, table } = designTokens

export const DSC_TOKENS = Object.freeze({
  primary: colors.primary,
  primaryDeep: colors.primaryDeep,
  primarySoft: colors.primarySoft,
  accent: colors.accent,
  accentDeep: colors.accentDeep,
  teal: colors.analytics,
  tealDeep: colors.analyticsDeep,
  bg: colors.background,
  bgDeep: colors.backgroundDeep,
  bgGradientTop: colors.primaryDeep,
  panel: colors.surface,
  panelElevated: colors.surfaceElevated,
  text: colors.text,
  muted: colors.muted,
  line: colors.border,
  accentOn: '#111827',
  primaryOn: '#FFFFFF',
  green: colors.success,
  amber: colors.warning,
  red: colors.critical,
  radiusCard: radius.card,
  radiusFrame: radius.frame,
  fontFamily: typography.fontFamily,
})

/** Alias preservado para retrocompatibilidade com componentes existentes. */
export const FIGMA_TOKENS = DSC_TOKENS

/**
 * Escala tipográfica, de espaçamento, z-index e densidade de tabela.
 * Use estes tokens em vez de `font-size`/`padding`/`margin`/`z-index` soltos
 * em componentes — eles espelham as variáveis CSS equivalentes em `styles.css`
 * (--font-size-*, --space-*, --z-*) para uso em lógica JS/inline styles quando
 * uma classe utilitária do Vuetify não for suficiente.
 */
export const DSC_TYPOGRAPHY_SCALE = Object.freeze({ ...typography.scale })
export const DSC_SPACING = Object.freeze({ ...spacing })
export const DSC_Z_INDEX = Object.freeze({ ...zIndex })
export const DSC_TABLE = Object.freeze({ ...table })

export const figmaVuetifyTheme = {
  dark: true,
  colors: {
    background: DSC_TOKENS.bg,
    surface: DSC_TOKENS.panel,
    'surface-variant': DSC_TOKENS.panelElevated,
    'surface-bright': DSC_TOKENS.bgGradientTop,
    primary: DSC_TOKENS.primary,
    secondary: DSC_TOKENS.teal,
    accent: DSC_TOKENS.accent,
    error: DSC_TOKENS.red,
    warning: DSC_TOKENS.amber,
    info: DSC_TOKENS.primary,
    success: DSC_TOKENS.green,
    'on-background': DSC_TOKENS.text,
    'on-surface': DSC_TOKENS.text,
    'on-primary': DSC_TOKENS.primaryOn,
    'on-secondary': '#001F2E',
    'on-error': '#FFFFFF',
  },
}

export const figmaVuetifyLightTheme = {
  dark: false,
  colors: {
    background: '#F6F8FB',
    surface: '#FFFFFF',
    'surface-variant': DSC_TOKENS.primarySoft,
    'surface-bright': '#FFFFFF',
    primary: DSC_TOKENS.primary,
    secondary: DSC_TOKENS.tealDeep,
    accent: DSC_TOKENS.accent,
    error: DSC_TOKENS.red,
    warning: DSC_TOKENS.accentDeep,
    info: DSC_TOKENS.primary,
    success: '#16803A',
    'on-background': '#111827',
    'on-surface': '#111827',
    'on-primary': DSC_TOKENS.primaryOn,
    'on-secondary': '#FFFFFF',
    'on-error': '#FFFFFF',
  },
}
