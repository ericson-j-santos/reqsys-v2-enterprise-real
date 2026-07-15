import { describe, expect, it } from 'vitest'
import { extractGovBIRows, isEmptyGovBIResponse } from '../api'

describe('integração de estado vazio GovBI', () => {
  it('extrai linhas do contrato normalizado', () => {
    expect(extractGovBIRows({ resultado: { linhas: [{ total: 1 }] } })).toHaveLength(1)
    expect(extractGovBIRows({ data: { resultado: { linhas: [] } } })).toEqual([])
  })

  it('detecta somente POST GovBI sem linhas', () => {
    expect(isEmptyGovBIResponse({
      config: { url: '/govbi/perguntas', method: 'post' },
      data: { resultado: { linhas: [] } },
    })).toBe(true)

    expect(isEmptyGovBIResponse({
      config: { url: '/govbi/perguntas', method: 'post' },
      data: { resultado: { linhas: [{ valor: 1 }] } },
    })).toBe(false)

    expect(isEmptyGovBIResponse({
      config: { url: '/dashboard/resumo', method: 'get' },
      data: { linhas: [] },
    })).toBe(false)
  })
})