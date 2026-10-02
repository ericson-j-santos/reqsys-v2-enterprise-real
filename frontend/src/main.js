import { createApp } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import App from './App.vue'
import router from './router'
import './styles.css'
import './responsive-pareto.css'
import './accessibility/wcag22-aa.css'
import { installWcag22Guard } from './accessibility/wcag22Guard'
import { useAuthStore } from './stores/auth'
import { api } from './services/api'
import { acquireIdTokenSilent, handleRedirectResult } from './auth/msal'
import { isMicrosoftRedirectResponse } from './auth/msalRedirectHandoff'
import { DSC_TABLE, DSC_Z_INDEX, figmaVuetifyLightTheme, figmaVuetifyTheme } from './theme/figmaPadraoOuro'

const temaPersistido = localStorage.getItem('reqsys_tema_visual')
const temaInicial = temaPersistido === 'reqsysClaro' ? 'reqsysClaro' : 'figmaPadraoOuro'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: temaInicial,
    themes: {
      figmaPadraoOuro: figmaVuetifyTheme,
      reqsysClaro: figmaVuetifyLightTheme,
    },
  },
  defaults: {
    VDataTable: { density: DSC_TABLE.density },
    VDataTableServer: { density: DSC_TABLE.density },
    VTable: { density: DSC_TABLE.density },
    VTextField: { density: 'comfortable' },
    VSelect: { density: 'comfortable' },
    VBtn: { density: 'comfortable' },
    VTooltip: { location: 'top', openDelay: 200, attach: false, zIndex: DSC_Z_INDEX.tooltip },
  },
})

function caminhoAtual() {
  return `${window.location.pathname}${window.location.search}${window.location.hash}`
}

function destinoSeguroAposLogin(caminhoInicial, retornoMicrosoft = false) {
  if (retornoMicrosoft) return '/'
  const redirect = router.currentRoute.value?.query?.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    return redirect
  }
  if (caminhoInicial.startsWith('/') && !caminhoInicial.startsWith('//') && !caminhoInicial.startsWith('/login')) {
    return caminhoInicial
  }
  return '/'
}

async function inicializarAutenticacao(caminhoInicial, retornoMicrosoft = false) {
  try {
    let idToken = await handleRedirectResult()
    if (!idToken && !useAuthStore().autenticado) {
      idToken = await acquireIdTokenSilent()
    }
    if (!idToken) {
      if (retornoMicrosoft) {
        throw new Error('O retorno Microsoft chegou ao ReqSys, mas não produziu um ID token. Código: MSAL_CALLBACK_WITHOUT_ID_TOKEN')
      }
      return
    }

    const { data } = await api.post('/v1/auth/azure', { id_token: idToken })
    useAuthStore().salvarSessao(data.data)
    localStorage.removeItem('azure_login_error')

    const destino = destinoSeguroAposLogin(caminhoInicial, retornoMicrosoft)
    if (router.currentRoute.value.fullPath !== destino) {
      await router.replace(destino)
    }
  } catch (e) {
    const errorCode = e.errorCode || e.code || e.response?.status
    const baseMessage = e.response?.data?.detail || e.message || 'Falha no acesso Microsoft'
    const msg = errorCode && !baseMessage.includes(String(errorCode))
      ? `${baseMessage} Código: ${errorCode}`
      : baseMessage
    sessionStorage.setItem('azure_login_error', msg)
    localStorage.setItem('azure_login_error', msg)
  }
}

async function boot() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const caminhoInicial = caminhoAtual()
  const retornoMicrosoft = isMicrosoftRedirectResponse(window.location)
  const app = createApp(App).use(pinia).use(vuetify)

  // No retorno OAuth, o MSAL precisa consumir code/state antes que o guard do
  // router redirecione para /login e remova esses parametros da URL.
  if (retornoMicrosoft) {
    await inicializarAutenticacao(caminhoInicial, true)
  }

  // Fora do retorno OAuth, a interface deve existir antes de chamadas externas
  // de autenticacao. Assim, atraso/falha do MSAL nunca deixa a tela em branco.
  // Monta antes da resolução assíncrona da rota inicial. Isso mantém o
  // comportamento de foco dos deep links e evita bloquear a interface.
  app.use(router)
  installWcag22Guard(router)
  app.mount('#app')

  if (!retornoMicrosoft) void inicializarAutenticacao(caminhoInicial)
}

boot().catch((error) => {
  const root = document.getElementById('app')
  if (root) {
    root.innerHTML = '<main style="font-family:Arial,sans-serif;padding:24px"><h1>ReqSys não iniciou</h1><p>Atualize a página. Se o problema continuar, o ambiente local precisa ser revalidado.</p></main>'
  }
  console.error('reqsys_boot_failed', error)
})
