import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '../PageHeader.vue'

describe('PageHeader', () => {
  it('renderiza o título no h1', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Requisitos' } })
    expect(wrapper.find('h1').text()).toBe('Requisitos')
  })

  it('renderiza o subtítulo quando fornecido', () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Requisitos', subtitle: 'Cadastre solicitações.' },
    })
    expect(wrapper.find('.page-header__subtitle').exists()).toBe(true)
    expect(wrapper.text()).toContain('Cadastre solicitações.')
  })

  it('omite o subtítulo quando não fornecido', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Requisitos' } })
    expect(wrapper.find('.page-header__subtitle').exists()).toBe(false)
  })

  it('renderiza o chip com a cor informada quando a prop chip é fornecida', () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Pipeline', chip: 'Demo', chipColor: 'blue' },
    })
    const chip = wrapper.findComponent({ name: 'VChip' })
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('Demo')
    expect(chip.props('color')).toBe('blue')
  })

  it('não renderiza chip quando a prop chip está vazia', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Pipeline' } })
    expect(wrapper.findComponent({ name: 'VChip' }).exists()).toBe(false)
  })

  it('renderiza o conteúdo do slot actions', () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Requisitos' },
      slots: { actions: '<button class="acao-teste">Novo</button>' },
    })
    expect(wrapper.find('.acao-teste').exists()).toBe(true)
  })
})
