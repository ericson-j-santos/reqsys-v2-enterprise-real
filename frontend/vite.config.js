import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendProxyTarget = process.env.VITE_BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000'
const kbProxyTarget = process.env.VITE_KB_PROXY_TARGET || 'http://127.0.0.1:8080'

/** Rotas FastAPI que já incluem o prefixo /api no backend — não remover no proxy dev. */
const BACKEND_API_PREFIXES = ['govbi', 'rag', 'requisitos', 'workflows', 'runtime']

function rewriteBackendProxyPath(path) {
  if (new RegExp(`^/api/(${BACKEND_API_PREFIXES.join('|')})\\b`).test(path)) {
    return path
  }
  return path.replace(/^\/api/, '')
}

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    clearMocks: true,
    setupFiles: ['./src/test/setup.js'],
    // Apenas testes unitários do app; os specs Playwright em tests/e2e usam outro runner.
    include: ['src/**/*.{test,spec}.{js,mjs,ts}'],
    exclude: ['node_modules/**', 'dist/**', 'tests/e2e/**'],
    server: {
      deps: { inline: ['vuetify'] },
    },
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage',
      reporter: ['text', 'text-summary', 'json-summary', 'html'],
      include: ['src/**/*.{js,vue}'],
      exclude: [
        'src/**/*.{test,spec}.{js,mjs,ts}',
        'src/test/**',
        'src/main.js',
      ],
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Proxy para acesso direto ao Vite (sem nginx) — ex: desenvolvimento isolado
    // Quando nginx está no ar (executar-local), o browser usa /api via nginx:8081
    proxy: {
      '/api': {
        target: backendProxyTarget,
        rewrite: rewriteBackendProxyPath,
        changeOrigin: true,
      },
      '/kb': {
        target: kbProxyTarget,
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
