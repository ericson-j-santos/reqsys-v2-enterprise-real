/**
 * useAsyncLoader — composable padrão para operações assíncronas com estado de carregamento e erro.
 *
 * Uso:
 *   const { carregando, erro, run } = useAsyncLoader()
 *   await run(async () => { dados.value = await api.get('/...') })
 *
 * Parâmetros de run(fn, { onError }):
 *   fn       — função async que executa a operação
 *   onError  — callback opcional chamado com o erro capturado
 */
import { ref } from 'vue'

export function useAsyncLoader() {
    const carregando = ref(false)
    const erro = ref('')

    async function run(fn, { onError } = {}) {
        carregando.value = true
        erro.value = ''
        try {
            await fn()
        } catch (e) {
            const mensagem =
                e?.response?.data?.errors?.[0]?.message ||
                e?.response?.data?.detail ||
                e?.message ||
                'Ocorreu um erro inesperado.'
            erro.value = mensagem
            if (onError) onError(e, mensagem)
        } finally {
            carregando.value = false
        }
    }

    return { carregando, erro, run }
}
