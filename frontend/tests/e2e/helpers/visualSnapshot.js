const { expect } = require('@playwright/test')
const { waitForPageStable } = require('./evidence')

/** Viewport fixo — snapshots só são comparáveis com a mesma resolução. */
const STABLE_VIEWPORT = { width: 1366, height: 768 }

/** Tolerância padrão para diferenças de anti-aliasing e subpixel. */
const DEFAULT_SNAPSHOT_OPTIONS = {
  animations: 'disabled',
  maxDiffPixelRatio: Number(process.env.E2E_VISUAL_MAX_DIFF_RATIO || 0.02),
  threshold: Number(process.env.E2E_VISUAL_THRESHOLD || 0.25),
  caret: 'hide',
}

const STABILITY_CSS = `
  *, *::before, *::after {
    animation-duration: 0s !important;
    animation-delay: 0s !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
    scroll-behavior: auto !important;
  }
  html { scroll-behavior: auto !important; }
`

async function injectVisualStability(page) {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.addStyleTag({ content: STABILITY_CSS })
}

async function prepareVisualPage(page, { viewport = STABLE_VIEWPORT } = {}) {
  await page.setViewportSize(viewport)
  await injectVisualStability(page)
}

/**
 * Compara captura contra baseline versionado (toHaveScreenshot).
 * Baselines ficam em visual-regression.spec.js-snapshots/.
 */
async function assertVisualSnapshot(page, name, options = {}) {
  const {
    locator = page.locator('body'),
    mask = [],
    fullPage = false,
    snapshotOptions = {},
  } = options

  await waitForPageStable(page)

  await expect(locator).toHaveScreenshot(`${name}.png`, {
    ...DEFAULT_SNAPSHOT_OPTIONS,
    fullPage,
    mask,
    ...snapshotOptions,
  })
}

module.exports = {
  STABLE_VIEWPORT,
  DEFAULT_SNAPSHOT_OPTIONS,
  prepareVisualPage,
  injectVisualStability,
  assertVisualSnapshot,
}
