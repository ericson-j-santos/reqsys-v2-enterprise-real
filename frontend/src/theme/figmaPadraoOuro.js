/**
 * Tokens e tema Vuetify alinhados ao DSC atual do ReqSys.
 *
 * Decisão de marca:
 * - Azul DSC como cor primária institucional.
 * - Laranja DSC como ação/destaque executivo.
 * - Turquesa DSC como apoio informacional e analytics.
 *
 * Mantém compatibilidade com o nome histórico `figmaPadraoOuro`
 * para não quebrar persistência local nem seleção de tema existente.
 */
export const DSC_TOKENS = {
  primary: '#005CA9',
  primaryDeep: '#003B73',
  primarySoft: '#E6F0FA',
  accent: '#F39200',
  accentDeep: '#B56D00',
  teal: '#00B3AD',
  tealDeep: '#007C78',
  bg: '#071526',
  bgDeep: '#03101F',
  bgGradientTop: '#062A4F',
  panel: '#0B2038',
  panelElevated: '#102B49',
  text: '#F8FAFC',
  muted: '#B8C7D9',
  line: 'rgba(184, 199, 217, 0.24)',
  accentOn: '#111827',
  primaryOn: '#FFFFFF',
  green: '#22C55E',
  amber: '#F59E0B',
  red: '#EF4444',
  radiusCard: '16px',
  radiusFrame: '24px',
  fontFamily: 'Inter, system-ui, sans-serif',
}

/** Alias preservado para retrocompatibilidade com componentes existentes. */
export const FIGMA_TOKENS = DSC_TOKENS

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
    error: '#DC2626',
    warning: DSC_TOKENS.accentDeep,
    info: DSC_TOKENS.primary,
    success: '#16803A',
    'on-background': '#111827',
    'on-surface': '#111827',
    'on-primary': DSC_TOKENS.primaryOn,
    'on-secondary': '#FFFFFF',
  },
}
