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

function destinoSeguroAposLogin(caminhoInicial) {
  const redirect = router.currentRoute.value?.query?.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    return redirect
  }
  if (caminhoInicial.startsWith('/') && !caminhoInicial.startsWith('//') && !caminhoInicial.startsWith('/login')) {
    return caminhoInicial
  }
  return '/'
}

async function inicializarAutenticacao(caminhoInicial) {
  try {
    let idToken = await handleRedirectResult()
    if (!idToken && !useAuthStore().autenticado) {
      idToken = await acquireIdTokenSilent()
    }
    if (!idToken) return

    const { data } = await api.post('/v1/auth/azure', { id_token: idToken })
    useAuthStore().salvarSessao(data.data)

    const destino = destinoSeguroAposLogin(caminhoInicial)
    if (router.currentRoute.value.fullPath !== destino) {
      await router.replace(destino)
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || 'Falha no acesso Microsoft'
    sessionStorage.setItem('azure_login_error', msg)
  }
}

async function boot() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const caminhoInicial = caminhoAtual()
  const app = createApp(App).use(pinia).use(router).use(vuetify)

  // A interface deve existir antes de qualquer chamada externa de autenticacao.
  // Assim, atraso/falha do MSAL nunca deixa o usuario preso em tela branca:
  // a rota protegida cai no login e, quando o SSO concluir, volta ao destino.
  await router.isReady()
  app.mount('#app')
  installWcag22Guard(router)

  void inicializarAutenticacao(caminhoInicial)
}

boot().catch((error) => {
  const root = document.getElementById('app')
  if (root) {
    root.innerHTML = '<main style="font-family:Arial,sans-serif;padding:24px"><h1>ReqSys não iniciou</h1><p>Atualize a página. Se o problema continuar, o ambiente local precisa ser revalidado.</p></main>'
  }
  console.error('reqsys_boot_failed', error)
})
