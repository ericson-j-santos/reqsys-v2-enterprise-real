import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Proxy para acesso direto ao Vite (sem nginx) — ex: desenvolvimento isolado
    // Quando nginx está no ar (executar-local), o browser usa /api via nginx:8081
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        rewrite: path => path.replace(/^\/api/, ''),
        changeOrigin: true,
      },
      '/kb': {
        target: 'http://127.0.0.1:8080',
        rewrite: path => path.replace(/^\/kb/, ''),
        changeOrigin: true,
      },
    },
    hmr: {
      protocol: 'ws',
      host: 'localhost',
      // clientPort = porta do gateway (nginx) que o browser usa para HMR
      clientPort: Number(process.env.GATEWAY_PORT) || 8081,
    },
    allowedHosts: true,
  },
})
