import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import App from './App.vue'
import router from './router'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'reqsysDark',
    themes: {
      reqsysDark: {
        dark: true,
        colors: {
          background: '#0d1117',
          surface: '#161b22',
          'surface-variant': '#21262d',
          primary: '#fbbf24',
          secondary: '#6366f1',
          accent: '#22d3ee',
          error: '#f87171',
          warning: '#fb923c',
          info: '#38bdf8',
          success: '#4ade80',
          'on-background': '#e6edf3',
          'on-surface': '#c9d1d9',
        }
      }
    }
  },
  defaults: {
    VBtn: { rounded: 'lg' },
    VCard: { rounded: 'lg' },
    VTextField: { rounded: 'lg' },
    VSelect: { rounded: 'lg' },
    VTextarea: { rounded: 'lg' },
  }
})

createApp(App).use(createPinia()).use(router).use(vuetify).mount('#app')
