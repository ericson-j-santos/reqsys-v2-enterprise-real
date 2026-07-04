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
import { useAuthStore } from './stores/auth'
import { api } from './services/api'
import { handleRedirectResult } from './auth/msal'
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
    const idToken = await handleRedirectResult()
    if (idToken) {
      const { data } = await api.post('/v1/auth/azure', { id_token: idToken })
      useAuthStore().salvarSessao(data.data)
      window.history.replaceState({}, document.title, '/')
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || 'Falha no login Microsoft'
    sessionStorage.setItem('azure_login_error', msg)
    window.history.replaceState({}, document.title, '/login')
  }

  createApp(App).use(pinia).use(router).use(vuetify).mount('#app')
}

boot()
