const STORAGE_TEMA = 'reqsys_nav_tema'
const STORAGE_SUBGRUPO = 'reqsys_nav_subgrupo_requisitos'

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
