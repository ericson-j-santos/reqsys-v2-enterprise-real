import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { FRONTEND_VERSION } from '../../constants/appVersion'
import { useAppVersion } from '../useAppVersion'

vi.mock('../../services/api', () => ({
  api: {
    get: vi.fn(),
  },
}))

import { api } from '../../services/api'

const TestHarness = defineComponent({
  setup() {
    return useAppVersion({ fetchOnMount: false })
  },
  template: '<div />',
})

describe('appVersion', () => {
  it('expõe versão do build', () => {
    expect(FRONTEND_VERSION).toBeTruthy()
    expect(typeof FRONTEND_VERSION).toBe('string')
  })
})

describe('useAppVersion', () => {
  it('usa versão do frontend quando API indisponível', async () => {
    api.get.mockRejectedValueOnce(new Error('offline'))

    const wrapper = mount(TestHarness)
    await wrapper.vm.loadRuntimeVersion()
    await nextTick()

    expect(wrapper.vm.versionLabel).toBe(`v${FRONTEND_VERSION}`)
    expect(wrapper.vm.apiVersion).toBeNull()
  })

  it('detecta alinhamento entre frontend e API', async () => {
    api.get.mockResolvedValueOnce({
      data: { data: { version: FRONTEND_VERSION, environment: 'development' } },
    })

    const wrapper = mount(TestHarness)
    await wrapper.vm.loadRuntimeVersion()
    await nextTick()

    expect(wrapper.vm.versionsAligned).toBe(true)
    expect(wrapper.vm.versionLabel).toBe(`v${FRONTEND_VERSION}`)
  })

  it('sinaliza divergência entre frontend e API', async () => {
    api.get.mockResolvedValueOnce({
      data: { data: { version: '9.9.9', environment: 'development' } },
    })

    const wrapper = mount(TestHarness)
    await wrapper.vm.loadRuntimeVersion()
    await nextTick()

    expect(wrapper.vm.versionsAligned).toBe(false)
    expect(wrapper.vm.versionLabel).toBe(`FE v${FRONTEND_VERSION} · API v9.9.9`)
  })
})
