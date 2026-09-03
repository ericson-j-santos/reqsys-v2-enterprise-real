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
import { useAuthStore } from './stores/auth'
import { api } from './services/api'
import { acquireIdTokenSilent, handleRedirectResult } from './auth/msal'
import { figmaVuetifyLightTheme, figmaVuetifyTheme } from './theme/figmaPadraoOuro'

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
})

async function boot() {
  const pinia = createPinia()
  setActivePinia(pinia)

  // Apps SPA trocam o codigo no browser; o backend apenas valida o id_token.
  try {
    let idToken = await handleRedirectResult()
    if (!idToken && !useAuthStore().autenticado) {
      // Sem redirect pendente e sem sessao ReqSys valida: tenta renovar
      // silenciosamente via SSO (conta Microsoft ja em cache, sem popup/
      // redirect visivel) antes de aceitar a tela de login. Cobre o caso de
      // reqsys_token expirado (1h) com a sessao Microsoft ainda ativa —
      // sem isso o usuario era jogado de volta ao login a cada expiracao.
      idToken = await acquireIdTokenSilent()
    }
    if (idToken) {
      const { data } = await api.post('/v1/auth/azure', { id_token: idToken })
      useAuthStore().salvarSessao(data.data)
      window.history.replaceState({}, document.title, '/')
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || 'Falha no acesso Microsoft'
    sessionStorage.setItem('azure_login_error', msg)
    window.history.replaceState({}, document.title, '/login')
  }

  createApp(App).use(pinia).use(router).use(vuetify).mount('#app')
}

boot()
