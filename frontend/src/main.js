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

  // ── Processar retorno do Azure AD ANTES do Vue Router correr ──────────
  // Microsoft redireciona de volta com ?code=... na URL principal.
  // Se processar depois, o router guard pode redirecionar e perder o código.
  const search = window.location.search
  if (search.includes('code=') || search.includes('error=')) {
    try {
      const { getMsalInstance, handleRedirectResult } = await import('./auth/msal.js')
      const msal = await getMsalInstance()
      if (msal) {
        const idToken = await handleRedirectResult()
        if (idToken) {
          const { data } = await api.post('/v1/auth/azure', { id_token: idToken })
          useAuthStore().salvarSessao(data.data)
        }
      }
    } catch (e) {
      console.warn('[MSAL boot]', e.message)
    }
    // Limpar params do OAuth da URL sem recarregar a página
    window.history.replaceState({}, document.title, window.location.pathname)
  }
  // ─────────────────────────────────────────────────────────────────────

  createApp(App).use(pinia).use(router).use(vuetify).mount('#app')
}

boot()
