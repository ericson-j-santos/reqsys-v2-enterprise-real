import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CatalogoAplicacoes from '../CatalogoAplicacoes.vue'
import { CATALOGO_APLICACOES, filtrarCatalogoAplicacoes } from '../../data/catalogoAplicacoes'

describe('Inventário de aplicações — governança e segurança', () => {
  it('preserva 15 identidades únicas e dados mínimos, sem declarar E2E indevido', () => {
    expect(CATALOGO_APLICACOES).toHaveLength(15)
    expect(new Set(CATALOGO_APLICACOES.map(item => item.id)).size).toBe(CATALOGO_APLICACOES.length)
    for (const item of CATALOGO_APLICACOES) {
      expect(item.id).toMatch(/^[A-Z][A-Z0-9-]+$/)
      expect(item.nome).toBeTruthy()
      expect(item.responsavel).toBeTruthy()
      expect(item.proximaAcao).toBeTruthy()
      expect(item.e2eComprovado).toBe(false)
      expect(['CODIGO_IDENTIFICADO', 'BRANCH_IDENTIFICADA', 'PUBLICADO_SEM_E2E']).toContain(item.estado)
    }
  })

  it('aceita apenas destinos públicos conhecidos e nenhum segredo na URL', () => {
    const publicados = CATALOGO_APLICACOES.filter(item => item.url)
    expect(publicados).toHaveLength(8)
    for (const item of publicados) {
      const destino = new URL(item.url)
      expect(destino.protocol).toBe('https:')
      expect(destino.hostname).toMatch(/^[a-z0-9-]+\.v2\.appdeploy\.ai$/)
      expect(destino.username).toBe('')
      expect(destino.password).toBe('')
      expect(destino.search).toBe('')
      expect(destino.hash).toBe('')
    }
  })

  it('filtra por palavra, por ID e ignora caixa; repetição não altera o inventário', () => {
    const baseline = JSON.stringify(CATALOGO_APLICACOES)
    expect(filtrarCatalogoAplicacoes(CATALOGO_APLICACOES, '  contratos ' ).length).toBeGreaterThan(0)
    expect(filtrarCatalogoAplicacoes(CATALOGO_APLICACOES, 'rEq-apP').map(item => item.id)).toEqual(['REQ-APP'])
    expect(filtrarCatalogoAplicacoes(CATALOGO_APLICACOES, 'sem-correspondencia-999')).toEqual([])
    expect(filtrarCatalogoAplicacoes(CATALOGO_APLICACOES, 'E2E')).toEqual(filtrarCatalogoAplicacoes(CATALOGO_APLICACOES, 'E2E'))
    expect(JSON.stringify(CATALOGO_APLICACOES)).toBe(baseline)
  })

  it('exibe a lista sem elevar implantação a funcionamento e mantém links externos seguros', () => {
    const wrapper = mount(CatalogoAplicacoes)
    expect(wrapper.findAll('[data-testid="catalogo-item"]')).toHaveLength(15)
    expect(wrapper.text()).toContain('funcionamento não comprovado')
    expect(wrapper.text()).toContain('Não comprovado')
    const links = wrapper.findAll('a[href*=".v2.appdeploy.ai"]')
    expect(links).toHaveLength(8)
    for (const link of links) {
      expect(link.attributes('target')).toBe('_blank')
      expect(link.attributes('rel')).toContain('noopener')
      expect(link.attributes('rel')).toContain('noreferrer')
    }
  })

  it('filtro vazio ou inexistente mostra estado verificável, sem falso sucesso', async () => {
    const wrapper = mount(CatalogoAplicacoes)
    const input = wrapper.get('#busca-catalogo-aplicacoes')
    await input.setValue('item que nao existe')
    expect(wrapper.findAll('[data-testid="catalogo-item"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('Nenhuma aplicação encontrada')
    await input.setValue('')
    expect(wrapper.findAll('[data-testid="catalogo-item"]')).toHaveLength(15)
  })
})
