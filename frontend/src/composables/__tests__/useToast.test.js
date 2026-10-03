import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useToast } from '../useToast'

describe('composables/useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // toasts é um singleton de módulo; zera entre testes.
    useToast().toasts.splice(0)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('success() adiciona um toast do tipo success', () => {
    const { success, toasts } = useToast()
    success('Salvo!')
    expect(toasts).toHaveLength(1)
    expect(toasts[0]).toMatchObject({ msg: 'Salvo!', type: 'success' })
  })

  it('remove o toast automaticamente após a duração padrão', () => {
    const { info, toasts } = useToast()
    info('Aguarde')
    expect(toasts).toHaveLength(1)
    vi.advanceTimersByTime(4000)
    expect(toasts).toHaveLength(0)
  })

  it('error() usa duração maior (6s)', () => {
    const { error, toasts } = useToast()
    error('Falhou')
    vi.advanceTimersByTime(4000)
    expect(toasts).toHaveLength(1)
    vi.advanceTimersByTime(2000)
    expect(toasts).toHaveLength(0)
  })

  it('remove(id) remove um toast específico', () => {
    const { warn, toasts, remove } = useToast()
    warn('A')
    warn('B')
    const idA = toasts[0].id
    remove(idA)
    expect(toasts.find(t => t.id === idA)).toBeUndefined()
    expect(toasts).toHaveLength(1)
  })

  it('atribui ids crescentes e distintos', () => {
    const { success, toasts } = useToast()
    success('1')
    success('2')
    expect(toasts[0].id).not.toBe(toasts[1].id)
  })
})
