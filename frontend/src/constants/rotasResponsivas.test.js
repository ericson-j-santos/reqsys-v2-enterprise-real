import { describe, expect, it } from 'vitest'
import { ROTAS_RESPONSIVAS } from './rotasResponsivas'

describe('rotasResponsivas', () => {
  it('define as 16 rotas operacionais canônicas', () => {
    expect(ROTAS_RESPONSIVAS).toHaveLength(16)
    expect(ROTAS_RESPONSIVAS.map((rota) => rota.testId)).not.toContain(undefined)
  })

  it('possui paths únicos', () => {
    const paths = ROTAS_RESPONSIVAS.map((rota) => rota.path)
    expect(new Set(paths).size).toBe(paths.length)
  })
})
