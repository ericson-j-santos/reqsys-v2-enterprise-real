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
createApp(App).use(createPinia()).use(router).use(vuetify).mount('#app')
