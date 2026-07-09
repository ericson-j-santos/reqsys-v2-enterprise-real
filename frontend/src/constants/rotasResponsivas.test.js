import { describe, expect, it } from 'vitest'
import { ROTAS_RESPONSIVAS } from './rotasResponsivas'
import { routes } from '../router'

const ROTAS_PUBLICAS_NAO_OPERACIONAIS = new Set(['/:pathMatch(.*)*'])

describe('rotasResponsivas', () => {
  it('define as rotas operacionais canônicas do catálogo', () => {
    expect(ROTAS_RESPONSIVAS.length).toBeGreaterThanOrEqual(29)
    expect(ROTAS_RESPONSIVAS.map((rota) => rota.testId)).not.toContain(undefined)
  })

  it('possui paths únicos', () => {
    const paths = ROTAS_RESPONSIVAS.map((rota) => rota.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('cobre todas as rotas operacionais registradas no roteador', () => {
    const pathsCatalogo = new Set(ROTAS_RESPONSIVAS.map((rota) => rota.path))
    const pathsRoteador = routes
      .map((rota) => rota.path)
      .filter((path) => !ROTAS_PUBLICAS_NAO_OPERACIONAIS.has(path))

    expect(pathsRoteador.filter((path) => !pathsCatalogo.has(path))).toEqual([])
  })
})
