import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusChip from '../StatusChip.vue'

function montar(props) {
  return mount(StatusChip, { props })
}

describe('StatusChip', () => {
  it('resolve label e cor do mapa padrão para um status conhecido', () => {
    const wrapper = montar({ value: 'aprovado' })
    expect(wrapper.text()).toContain('Aprovado')
    const chip = wrapper.findComponent({ name: 'VChip' })
    expect(chip.props('color')).toBe('green')
  })

  it('é case-insensitive em relação ao value', () => {
    const wrapper = montar({ value: 'PENDENTE' })
    expect(wrapper.text()).toContain('Pendente')
    expect(wrapper.findComponent({ name: 'VChip' }).props('color')).toBe('amber')
  })

  it('mapeia origem de segredo (vault → Cofre/green)', () => {
    const wrapper = montar({ value: 'vault' })
    expect(wrapper.text()).toContain('Cofre')
    expect(wrapper.findComponent({ name: 'VChip' }).props('color')).toBe('green')
  })

  it('faz fallback para o próprio value e cor grey quando desconhecido', () => {
    const wrapper = montar({ value: 'estado_inexistente' })
    expect(wrapper.text()).toContain('estado_inexistente')
    expect(wrapper.findComponent({ name: 'VChip' }).props('color')).toBe('grey')
  })

  it('permite sobrescrever o mapa padrão via prop map', () => {
    const wrapper = montar({
      value: 'aprovado',
      map: { aprovado: { label: 'OK', color: 'purple' } },
    })
    expect(wrapper.text()).toContain('OK')
    expect(wrapper.findComponent({ name: 'VChip' }).props('color')).toBe('purple')
  })

  it('aplica size e variant informados ao chip', () => {
    const wrapper = montar({ value: 'aprovado', size: 'x-large', variant: 'flat' })
    const chip = wrapper.findComponent({ name: 'VChip' })
    expect(chip.props('size')).toBe('x-large')
    expect(chip.props('variant')).toBe('flat')
  })

  it('renderiza tooltip quando a prop tooltip é fornecida', () => {
    const wrapper = montar({ value: 'aprovado', tooltip: 'Lido do cofre' })
    expect(wrapper.findComponent({ name: 'VTooltip' }).exists()).toBe(true)
  })
})
