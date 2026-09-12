import { describe, expect, it } from 'vitest'
import { NAV_TEMAS, itensDoSubgrupo, subgrupoIdPorRota, temaIdPorRota } from './navCatalog'

describe('ReqSys 360 — Administração', () => {
  it('divide Administração em subgrupos navegáveis com no máximo cinco opções', () => {
    const administracao = NAV_TEMAS.find((tema) => tema.id === 'administracao')
    expect(administracao?.subgroups?.map((subgrupo) => subgrupo.id)).toEqual([
      'operacao',
      'seguranca-governanca',
      'engenharia-ia',
    ])

    for (const subgrupo of administracao.subgroups) {
      expect(itensDoSubgrupo('administracao', subgrupo.id).length).toBeLessThanOrEqual(5)
    }
  })

  it('mantém todas as funções administrativas alcançáveis e no grupo correto', () => {
    const administracao = NAV_TEMAS.find((tema) => tema.id === 'administracao')
    const caminhos = new Set(administracao.subgroups.flatMap((subgrupo) => subgrupo.paths))
    expect(administracao.items.filter((item) => !caminhos.has(item.to))).toEqual([])

    expect(subgrupoIdPorRota('/monitoramento-operacional')).toBe('operacao')
    expect(subgrupoIdPorRota('/admin/session-management')).toBe('seguranca-governanca')
    expect(subgrupoIdPorRota('/orquestrador-ia')).toBe('engenharia-ia')
    expect(temaIdPorRota('/admin/github-merge')).toBe('administracao')
  })
})
