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

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'institucional',
    themes: {
      institucional: {
        dark: false,
        colors: {
          background: '#FFFFFF',
          surface: '#FFFFFF',
          'surface-variant': '#E8F1FA',
          primary: '#005CA9',
          secondary: '#F39200',
          accent: '#00B3AD',
          error: '#C62828',
          warning: '#F57C00',
          info: '#0277BD',
          success: '#2E7D32',
          'on-background': '#333333',
          'on-surface': '#333333',
        },
      },
    },
  },
})

async function boot() {
  const pinia = createPinia()
  setActivePinia(pinia) // permite usar stores antes do app montar

  // ── Inicializar MSAL SEMPRE ao startup ────────────────────────────────
  // handleRedirectPromise() DEVE ser chamado em todo carregamento de página,
  // não só quando ?code= está na URL. Isso garante que:
  //  1. Qualquer retorno de redirect do Microsoft é processado
  //  2. Estado de interação travado (interaction_in_progress) é limpo
  try {
    const { getMsalInstance, handleRedirectResult } = await import('./auth/msal.js')
    const msal = await getMsalInstance()
    if (msal) {
      const idToken = await handleRedirectResult()
      if (idToken) {
        const { data } = await api.post('/v1/auth/azure', { id_token: idToken })
        useAuthStore().salvarSessao(data.data)
        window.history.replaceState({}, document.title, window.location.pathname)
      }
    }
  } catch (e) {
    console.warn('[MSAL boot]', e.message)
  }
  // ─────────────────────────────────────────────────────────────────────

  createApp(App).use(pinia).use(router).use(vuetify).mount('#app')
}

boot()
