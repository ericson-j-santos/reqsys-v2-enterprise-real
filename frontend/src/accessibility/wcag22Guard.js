const SCROLLABLE_REGIONS = [
  ['[data-testid="route-task-console"] .payload-box', 'Prévia do payload enviado ao Flow'],
  ['[data-testid="route-figma-github"] .json-retorno', 'Retorno JSON da última sincronização'],
  ['[data-testid="route-figma-github"] .tabela-wrapper', 'Tabela de vínculos entre Figma e GitHub'],
  ['[data-testid="route-specs"] .content-body', 'Conteúdo da especificação'],
  ['[data-testid="route-specs"] .code-block', 'Bloco de código da especificação'],
  ['[data-testid="route-specs"] .mermaid-block', 'Diagrama Mermaid da especificação'],
]

const ICON_BUTTON_NAMES = new Map([
  ['mdi-refresh', 'Atualizar'],
  ['mdi-eye-outline', 'Visualizar relatório'],
  ['mdi-open-in-new', 'Abrir em nova guia'],
  ['mdi-file-pdf-box', 'Baixar relatório em PDF'],
  ['mdi-robot-outline', 'Gerar recomendação com IA'],
  ['mdi-delete-outline', 'Remover tarefa'],
])

function normalizeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function hasAccessibleName(element) {
  return Boolean(
    normalizeText(element.getAttribute('aria-label')) ||
    normalizeText(element.getAttribute('aria-labelledby')) ||
    normalizeText(element.getAttribute('title')) ||
    normalizeText(element.textContent),
  )
}

function getDescribedName(element, root) {
  const ids = normalizeText(element.getAttribute('aria-describedby')).split(' ').filter(Boolean)
  for (const id of ids) {
    const described = root.getElementById?.(id)
    const name = normalizeText(described?.getAttribute?.('aria-label') || described?.textContent)
    if (name) return name
  }
  return ''
}

function getIconButtonName(button) {
  for (const [iconClass, label] of ICON_BUTTON_NAMES) {
    if (button.querySelector(`.${iconClass}`)) return label
  }
  return ''
}

function contextualProgressName(progress) {
  const route = progress.closest('[data-testid]')?.getAttribute('data-testid')

  if (route === 'route-painel-integracao') {
    return 'Uso da capacidade diária do Flow bot'
  }

  if (route === 'route-qualidade-ia') {
    if (progress.closest('.score-wrap')) return 'Score geral de qualidade de IA'

    const metric = progress.closest('.v-col')?.querySelector('.metric-head-row span')
    if (normalizeText(metric?.textContent)) return `Métrica de qualidade: ${normalizeText(metric.textContent)}`

    const provider = progress.closest('.v-col')?.querySelector('.provider-header strong')
    if (normalizeText(provider?.textContent)) return `Uso diário do provedor ${normalizeText(provider.textContent)}`

    return 'Indicador de qualidade de IA'
  }

  return 'Indicador de progresso'
}

export function applyWcag22Guard(root = document) {
  if (!root?.querySelectorAll) return

  for (const progress of root.querySelectorAll('[role="progressbar"]')) {
    if (!hasAccessibleName(progress)) {
      progress.setAttribute('aria-label', contextualProgressName(progress))
    }
  }

  for (const button of root.querySelectorAll('button')) {
    if (hasAccessibleName(button)) continue

    const describedName = getDescribedName(button, root)
    const iconName = getIconButtonName(button)
    const name = describedName || iconName
    if (name) button.setAttribute('aria-label', name)
  }

  for (const [selector, label] of SCROLLABLE_REGIONS) {
    for (const region of root.querySelectorAll(selector)) {
      if (!region.hasAttribute('tabindex')) region.setAttribute('tabindex', '0')
      if (!region.hasAttribute('aria-label') && !region.hasAttribute('aria-labelledby')) {
        region.setAttribute('aria-label', label)
      }
    }
  }
}

export function installWcag22Guard(router, root = document) {
  let scheduled = false
  const schedule = () => {
    if (scheduled) return
    scheduled = true
    const run = () => {
      scheduled = false
      applyWcag22Guard(root)
    }
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(run)
    else queueMicrotask(run)
  }

  applyWcag22Guard(root)
  router?.afterEach?.(schedule)

  const target = root.getElementById?.('app') || root.body
  if (target && typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(schedule)
    observer.observe(target, { childList: true, subtree: true })
    return () => observer.disconnect()
  }

  return () => {}
}
