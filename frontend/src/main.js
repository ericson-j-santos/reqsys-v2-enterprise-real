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
    // Densidade única de tabela (design-tokens.json#table) — nenhuma tela
    // precisa mais escolher `density` individualmente. Não alteramos `variant`
    // aqui de propósito: mudar o estilo visual padrão de inputs em todo o app
    // exige validação visual tela a tela, fora do escopo desta correção.
    VDataTable: { density: DSC_TABLE.density },
    VDataTableServer: { density: DSC_TABLE.density },
    VTable: { density: DSC_TABLE.density },
    VTextField: { density: 'comfortable' },
    VSelect: { density: 'comfortable' },
    VBtn: { density: 'comfortable' },
    // attach:false + zIndex explícito: sem `attach`, VOverlay.useTeleport só
    // teleporta para `.v-overlay-container` no <body> quando `attach === false`
    // (não quando é apenas "não definido") — sem isso, o tooltip renderiza
    // `position:absolute` inline dentro da árvore do componente, sujeito à
    // ordem normal de pintura entre irmãos no DOM (não a um stacking context
    // de overlay real), e qualquer conteúdo de página renderizado depois no
    // DOM pode cobri-lo mesmo com z-index alto. VTooltip também roda com
    // `_disableGlobalStack`, então nunca sobe acima do zIndex padrão (2000)
    // da Vuetify sozinho — sem esse zIndex explícito, toast/alerta de
    // conectividade/route-feedback do app (z-index 3000-5000) cobririam o
    // tooltip sempre que se sobrepusessem na tela.
    VTooltip: { location: 'top', openDelay: 200, attach: false, zIndex: DSC_Z_INDEX.tooltip },
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
