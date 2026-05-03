import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import App from './App.vue'
import router from './router'
import './styles.css'

const vuetify = createVuetify({ components, directives, theme: { defaultTheme: 'dark' } })
createApp(App).use(createPinia()).use(router).use(vuetify).mount('#app')
