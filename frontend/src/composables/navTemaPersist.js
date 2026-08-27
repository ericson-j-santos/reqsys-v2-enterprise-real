const STORAGE_TEMA = 'reqsys_nav_tema'
const STORAGE_SUBGRUPO = 'reqsys_nav_subgrupo_requisitos'
const STORAGE_SIDEBAR_COLAPSADO = 'reqsys_sidebar_colapsado'

export function lerTemaPersistido() {
  try {
    return sessionStorage.getItem(STORAGE_TEMA) || null
  } catch {
    return null
  }
}

export function salvarTemaPersistido(temaId) {
  try {
    if (temaId) sessionStorage.setItem(STORAGE_TEMA, temaId)
  } catch {
    /* silencioso */
  }
}

export function lerSubgrupoRequisitosPersistido() {
  try {
    return sessionStorage.getItem(STORAGE_SUBGRUPO) || null
  } catch {
    return null
  }
}

export function salvarSubgrupoRequisitosPersistido(subgrupoId) {
  try {
    if (subgrupoId) sessionStorage.setItem(STORAGE_SUBGRUPO, subgrupoId)
  } catch {
    /* silencioso */
  }
}

export function lerSidebarColapsadoPersistido() {
  try {
    return localStorage.getItem(STORAGE_SIDEBAR_COLAPSADO) === '1'
  } catch {
    return false
  }
}

export function salvarSidebarColapsadoPersistido(colapsado) {
  try {
    localStorage.setItem(STORAGE_SIDEBAR_COLAPSADO, colapsado ? '1' : '0')
  } catch {
    /* silencioso */
  }
}
