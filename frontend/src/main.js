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
import { extractOAuthCallback } from './auth/azure'

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
  setActivePinia(pinia)

  // ── Processar retorno do Azure AD antes do Vue Router correr ─────────
  const callback = extractOAuthCallback()
  if (callback) {
    if (callback.error) {
      sessionStorage.setItem('azure_login_error', callback.error)
    } else {
      try {
        const { data } = await api.post('/v1/auth/azure-code', callback)
        useAuthStore().salvarSessao(data.data)
      } catch (e) {
        const msg = e.response?.data?.detail || e.message || 'Falha no login Microsoft'
        sessionStorage.setItem('azure_login_error', msg)
      }
    }
    // Limpar parâmetros OAuth da URL sem recarregar
    window.history.replaceState({}, document.title, '/')
  }
  // ────────────────────────────────────────────────────────────────────

  createApp(App).use(pinia).use(router).use(vuetify).mount('#app')
}

boot()
