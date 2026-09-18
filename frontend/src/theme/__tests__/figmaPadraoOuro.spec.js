import { describe, expect, it } from 'vitest'

import designTokens from '../design-tokens.json'
import {
  DSC_TOKENS,
  FIGMA_TOKENS,
  figmaVuetifyLightTheme,
  figmaVuetifyTheme,
} from '../figmaPadraoOuro'

describe('contrato de design tokens Figma/DSC', () => {
  it('mantém o alias histórico apontando para o contrato runtime', () => {
    expect(FIGMA_TOKENS).toBe(DSC_TOKENS)
  })

  it('mapeia os tokens canônicos para o adaptador de compatibilidade', () => {
    expect(DSC_TOKENS).toMatchObject({
      primary: designTokens.colors.primary,
      primaryDeep: designTokens.colors.primaryDeep,
      primarySoft: designTokens.colors.primarySoft,
      accent: designTokens.colors.accent,
      accentDeep: designTokens.colors.accentDeep,
      teal: designTokens.colors.analytics,
      tealDeep: designTokens.colors.analyticsDeep,
      bg: designTokens.colors.background,
      bgDeep: designTokens.colors.backgroundDeep,
      panel: designTokens.colors.surface,
      panelElevated: designTokens.colors.surfaceElevated,
      text: designTokens.colors.text,
      muted: designTokens.colors.muted,
      line: designTokens.colors.border,
      green: designTokens.colors.success,
      amber: designTokens.colors.warning,
      red: designTokens.colors.critical,
      radiusCard: designTokens.radius.card,
      radiusFrame: designTokens.radius.frame,
      fontFamily: designTokens.typography.fontFamily,
    })
  })

  it('propaga tokens semânticos obrigatórios para os temas Vuetify', () => {
    expect(figmaVuetifyTheme).toMatchObject({
      dark: true,
      colors: {
        background: designTokens.colors.background,
        surface: designTokens.colors.surface,
        primary: designTokens.colors.primary,
        secondary: designTokens.colors.analytics,
        accent: designTokens.colors.accent,
        error: designTokens.colors.critical,
        warning: designTokens.colors.warning,
        success: designTokens.colors.success,
      },
    })

    expect(figmaVuetifyLightTheme).toMatchObject({
      dark: false,
      colors: {
        primary: designTokens.colors.primary,
        secondary: designTokens.colors.analyticsDeep,
        accent: designTokens.colors.accent,
        error: designTokens.colors.critical,
      },
    })
  })
})
