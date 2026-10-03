import { describe, expect, it } from 'vitest'

import {
  isRetiredFlyUrl,
  requireProviderNeutralRuntimeUrl,
} from './runtimeUrlPolicy'

describe('runtimeUrlPolicy', () => {
  it('rejeita hosts Fly.io e subdominios', () => {
    expect(isRetiredFlyUrl('https://reqsys-api.fly.dev')).toBe(true)
    expect(isRetiredFlyUrl('https://fly.io/apps')).toBe(true)
    expect(() => requireProviderNeutralRuntimeUrl('https://reqsys.fly.dev')).toThrow(
      'retirado definitivamente',
    )
  })

  it('preserva URLs relativas e endpoints provider-neutral', () => {
    expect(isRetiredFlyUrl('/api')).toBe(false)
    expect(requireProviderNeutralRuntimeUrl('https://reqsys.example.invalid')).toBe(
      'https://reqsys.example.invalid',
    )
  })
})
