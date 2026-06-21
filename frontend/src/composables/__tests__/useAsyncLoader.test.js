import { describe, it, expect, vi } from 'vitest'
import { useAsyncLoader } from '../useAsyncLoader'

describe('composables/useAsyncLoader', () => {
  it('inicia com carregando=false e erro vazio', () => {
    const { carregando, erro } = useAsyncLoader()
    expect(carregando.value).toBe(false)
    expect(erro.value).toBe('')
  })

  it('alterna carregando durante a execução e limpa ao final', async () => {
    const { carregando, run } = useAsyncLoader()
    let durante = null
    await run(async () => { durante = carregando.value })
    expect(durante).toBe(true)
    expect(carregando.value).toBe(false)
  })

  it('extrai mensagem de erros[].message da resposta da API', async () => {
    const { erro, run } = useAsyncLoader()
    await run(async () => {
      throw { response: { data: { errors: [{ message: 'campo inválido' }] } } }
    })
    expect(erro.value).toBe('campo inválido')
  })

  it('faz fallback para detail e depois para message', async () => {
    const loaderDetail = useAsyncLoader()
    await loaderDetail.run(async () => { throw { response: { data: { detail: 'sem permissão' } } } })
    expect(loaderDetail.erro.value).toBe('sem permissão')

    const loaderMsg = useAsyncLoader()
    await loaderMsg.run(async () => { throw new Error('erro genérico') })
    expect(loaderMsg.erro.value).toBe('erro genérico')
  })

  it('usa mensagem padrão quando o erro não tem informações', async () => {
    const { erro, run } = useAsyncLoader()
    await run(async () => { throw {} })
    expect(erro.value).toBe('Ocorreu um erro inesperado.')
  })

  it('chama onError com o erro e a mensagem resolvida', async () => {
    const onError = vi.fn()
    const { run } = useAsyncLoader()
    const err = { response: { data: { detail: 'boom' } } }
    await run(async () => { throw err }, { onError })
    expect(onError).toHaveBeenCalledWith(err, 'boom')
  })
})
