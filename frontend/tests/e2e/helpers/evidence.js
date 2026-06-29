const fs = require('node:fs')
const path = require('node:path')

const EVIDENCE_ROOT = process.env.E2E_EVIDENCE_DIR
  || path.join(process.cwd(), 'test-results', 'evidence')

function slugify(value) {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function isStagingTarget() {
  const base = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || ''
  return /fly\.dev|stg|staging/i.test(base)
}

function ensureEvidenceDir(subdir = '') {
  const target = subdir ? path.join(EVIDENCE_ROOT, subdir) : EVIDENCE_ROOT
  fs.mkdirSync(target, { recursive: true })
  return target
}

async function waitForPageStable(page, { timeout = 8000 } = {}) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForLoadState('networkidle', { timeout }).catch(() => {})
  await page.evaluate(async () => {
    if (document.fonts?.ready) {
      await document.fonts.ready
    }
  }).catch(() => {})
  await page.waitForTimeout(250)
}

async function captureEvidence(page, name, options = {}) {
  const {
    fullPage = true,
    subdir = '',
    mask = [],
    metadata = {},
  } = options

  const dir = ensureEvidenceDir(subdir)
  const slug = slugify(name)
  const filePath = path.join(dir, `${slug}.png`)

  await waitForPageStable(page)

  await page.screenshot({
    path: filePath,
    fullPage,
    mask,
  })

  const metaPath = path.join(dir, `${slug}.json`)
  fs.writeFileSync(metaPath, JSON.stringify({
    name,
    slug,
    url: page.url(),
    captured_at: new Date().toISOString(),
    viewport: page.viewportSize(),
    ...metadata,
  }, null, 2))

  return filePath
}

module.exports = {
  EVIDENCE_ROOT,
  isStagingTarget,
  slugify,
  ensureEvidenceDir,
  waitForPageStable,
  captureEvidence,
}
