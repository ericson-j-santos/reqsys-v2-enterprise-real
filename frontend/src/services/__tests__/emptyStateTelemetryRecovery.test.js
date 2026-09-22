import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readEmptyStateTelemetry, recordEmptyState, STORAGE_KEY } from '../emptyStateTelemetry'

describe('emptyStateTelemetry recovery duration', () => {
  beforeEach(() => {
    sessionStorage.removeItem(STORAGE_KEY)
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-15T12:00:00.000Z'))
  })

  it('calcula o tempo entre visualização e ação de recuperação', () => {
    recordEmptyState({ context: 'analytics', event: 'view' })
    vi.advanceTimersByTime(12500)
    const entry = recordEmptyState({ context: 'analytics', event: 'secondary_action' })

    expect(entry.recoveryDurationMs).toBe(12500)
    expect(readEmptyStateTelemetry()).toHaveLength(2)
  })

  it('não mistura contextos diferentes', () => {
    recordEmptyState({ context: 'analytics', event: 'view' })
    const entry = recordEmptyState({ context: 'monitoramento', event: 'primary_action' })
    expect(entry.recoveryDurationMs).toBeUndefined()
  })
})
