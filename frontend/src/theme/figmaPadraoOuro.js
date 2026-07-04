/** Tokens e tema Vuetify alinhados a docs/dashboard/figma/ (Padrão Ouro · Trilha C). */
export const FIGMA_TOKENS = {
  bg: '#0b1220',
  bgDeep: '#020617',
  bgGradientTop: '#0f172a',
  panel: '#111827',
  text: '#e5e7eb',
  muted: '#94a3b8',
  line: 'rgba(148, 163, 184, 0.28)',
  accent: '#f39200',
  accentOn: '#111827',
  green: '#22c55e',
  amber: '#f59e0b',
  red: '#ef4444',
  docs: '#38bdf8',
  radiusCard: '16px',
  radiusFrame: '24px',
  fontFamily: 'Inter, system-ui, sans-serif',
}

export const figmaVuetifyTheme = {
  dark: true,
  colors: {
    background: FIGMA_TOKENS.bg,
    surface: FIGMA_TOKENS.panel,
    'surface-variant': 'rgba(255,255,255,0.04)',
    'surface-bright': FIGMA_TOKENS.bgGradientTop,
    primary: FIGMA_TOKENS.accent,
    secondary: FIGMA_TOKENS.docs,
    accent: FIGMA_TOKENS.accent,
    error: FIGMA_TOKENS.red,
    warning: FIGMA_TOKENS.amber,
    info: FIGMA_TOKENS.docs,
    success: FIGMA_TOKENS.green,
    'on-background': FIGMA_TOKENS.text,
    'on-surface': FIGMA_TOKENS.text,
    'on-primary': FIGMA_TOKENS.accentOn,
  },
}

export const figmaVuetifyLightTheme = {
  dark: false,
  colors: {
    background: '#f6f8fb',
    surface: '#ffffff',
    'surface-variant': '#eef2f7',
    'surface-bright': '#ffffff',
    primary: FIGMA_TOKENS.accent,
    secondary: '#0ea5e9',
    accent: FIGMA_TOKENS.accent,
    error: '#dc2626',
    warning: '#d97706',
    info: '#0284c7',
    success: '#16a34a',
    'on-background': '#111827',
    'on-surface': '#111827',
    'on-primary': '#111827',
  },
}
