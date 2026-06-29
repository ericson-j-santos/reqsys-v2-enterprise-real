<template>
  <main class="figma-github" aria-labelledby="titulo-figma-github">
    <section class="cabecalho">
      <div>
        <p class="figma-eyebrow">ReqSys · Integração visual</p>
        <h1 id="titulo-figma-github">Figma GitHub</h1>
        <p>
          Painel operacional para sincronizar artefatos do Figma com GitHub e exibir retorno auditável em tela.
        </p>
      </div>
      <div class="acoes-cabecalho">
        <button type="button" :disabled="carregandoStatus" @click="carregarStatus">
          {{ carregandoStatus ? 'Atualizando...' : 'Atualizar status' }}
        </button>
      </div>
    </section>

    <p v-if="erro" class="alerta erro" role="alert">{{ erro }}</p>
    <p v-if="mensagem" class="alerta sucesso" role="status">{{ mensagem }}</p>

    <section class="cards" aria-label="Resumo da integração Figma GitHub">
      <article class="card">
        <span>Total vínculos</span>
        <strong>{{ resumo.total }}</strong>
      </article>
      <article class="card">
        <span>Sincronizados</span>
        <strong>{{ resumo.sincronizados }}</strong>
      </article>
      <article class="card">
        <span>Conflitos</span>
        <strong>{{ resumo.conflitos }}</strong>
      </article>
      <article class="card">
        <span>Última ação</span>
        <strong>{{ ultimaAcao }}</strong>
      </article>
    </section>

    <section class="painel" aria-labelledby="titulo-sincronizacao">
      <div>
        <h2 id="titulo-sincronizacao">Sincronização governada</h2>
        <p>
          Informe a chave do arquivo Figma e o repositório GitHub. Quando omitidos, o backend usa as configurações
          padrão seguras, caso estejam habilitadas no ambiente.
        </p>
      </div>

      <form class="formulario" @submit.prevent="sincronizar">
        <label>
          File key do Figma
          <input v-model.trim="form.file_key" type="text" placeholder="Opcional se FIGMA_DEFAULT_FILE_KEY existir" />
        </label>
        <label>
          Repositório GitHub
          <input v-model.trim="form.repo" type="text" placeholder="owner/repo" />
        </label>
        <label>
          Modo
          <select v-model="form.mode">
            <option value="bidirectional">Bidirecional</option>
            <option value="figma_to_github">Figma para GitHub</option>
            <option value="github_to_figma">GitHub para Figma</option>
          </select>
        </label>
        <label>
          Node IDs
          <input v-model.trim="nodeIdsTexto" type="text" placeholder="IDs separados por vírgula" />
        </label>

        <div class="checks">
          <label><input v-model="form.include_comments" type="checkbox" /> Comentários</label>
          <label><input v-model="form.include_frames" type="checkbox" /> Frames</label>
          <label><input v-model="form.include_dev_resources" type="checkbox" /> Dev resources</label>
        </div>

        <button type="submit" :disabled="sincronizando">
          {{ sincronizando ? 'Sincronizando...' : 'Executar sincronização' }}
        </button>
      </form>
    </section>

    <section v-if="resultadoSync" class="painel" aria-labelledby="titulo-retorno">
      <h2 id="titulo-retorno">Retorno da última sincronização</h2>
      <dl class="detalhes">
        <div><dt>File key</dt><dd>{{ resultadoSync.file_key || '-' }}</dd></div>
        <div><dt>Repositório</dt><dd>{{ resultadoSync.repo || '-' }}</dd></div>
        <div><dt>Modo</dt><dd>{{ resultadoSync.mode || '-' }}</dd></div>
        <div><dt>Status</dt><dd>{{ resultadoSync.status || 'processado' }}</dd></div>
      </dl>
      <pre class="json-retorno">{{ JSON.stringify(resultadoSync, null, 2) }}</pre>
    </section>

    <section class="painel" aria-labelledby="titulo-analitico">
      <div class="linha-painel">
        <div>
          <h2 id="titulo-analitico">Analítico de vínculos</h2>
          <p>Status retornado pelo backend para rastrear Figma, GitHub, conflitos e última sincronização.</p>
        </div>
        <label class="filtro">
          Status
          <select v-model="filtroStatus">
            <option value="">Todos</option>
            <option v-for="status in statusDisponiveis" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
      </div>

      <div class="tabela-wrapper">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Arquivo Figma</th>
              <th>Node</th>
              <th>Repositório</th>
              <th>Issue</th>
              <th>Tipo</th>
              <th>Status</th>
              <th>Conflito</th>
              <th>Última sync</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in itensFiltrados" :key="item.id">
              <td>{{ item.id }}</td>
              <td>{{ item.figma_file_key || '-' }}</td>
              <td>{{ item.figma_node_id || '-' }}</td>
              <td>{{ item.github_repo || '-' }}</td>
              <td>
                <a v-if="item.github_issue_url" :href="item.github_issue_url" target="_blank" rel="noopener noreferrer">
                  #{{ item.github_issue_number }}
                </a>
                <span v-else>{{ item.github_issue_number || '-' }}</span>
              </td>
              <td>{{ item.sync_kind || '-' }}</td>
              <td><span class="badge">{{ item.status || 'desconhecido' }}</span></td>
              <td>{{ item.conflict_reason || '-' }}</td>
              <td>{{ formatarData(item.last_synced_at) }}</td>
            </tr>
            <tr v-if="!itensFiltrados.length">
              <td colspan="9" class="vazio">Nenhum vínculo encontrado para o filtro atual.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../services/api'

const API_BASE = '/v1/integracoes/figma-github'

const form = reactive({
  file_key: '',
  repo: '',
  mode: 'bidirectional',
  include_comments: true,
  include_frames: true,
  include_dev_resources: true,
})

const nodeIdsTexto = ref('')
const filtroStatus = ref('')
const itens = ref([])
const resultadoSync = ref(null)
const carregandoStatus = ref(false)
const sincronizando = ref(false)
const erro = ref('')
const mensagem = ref('')
const ultimaAcao = ref('-')

const resumo = computed(() => {
  const total = itens.value.length
  const sincronizados = itens.value.filter((item) => ['synced', 'sincronizado', 'ok', 'success'].includes(String(item.status).toLowerCase())).length
  const conflitos = itens.value.filter((item) => item.conflict_reason || String(item.status).toLowerCase().includes('conflict')).length
  return { total, sincronizados, conflitos }
})

const statusDisponiveis = computed(() => [...new Set(itens.value.map((item) => item.status).filter(Boolean))].sort())
const itensFiltrados = computed(() => itens.value.filter((item) => !filtroStatus.value || item.status === filtroStatus.value))

function limparAlertas() {
  erro.value = ''
  mensagem.value = ''
}

function montarPayload() {
  return {
    file_key: form.file_key || null,
    repo: form.repo || null,
    mode: form.mode,
    node_ids: nodeIdsTexto.value.split(',').map((nodeId) => nodeId.trim()).filter(Boolean),
    include_comments: form.include_comments,
    include_frames: form.include_frames,
    include_dev_resources: form.include_dev_resources,
  }
}

async function carregarStatus() {
  carregandoStatus.value = true
  limparAlertas()
  try {
    const { data: payload } = await api.get(`${API_BASE}/status`)
    itens.value = payload.data?.items || []
    if (payload.data?.modo_degradado) {
      mensagem.value = 'Modo degradado: vínculos demonstrativos locais (tokens Figma/GitHub ausentes).'
    }
    ultimaAcao.value = new Date().toLocaleString('pt-BR')
  } catch (e) {
    erro.value = e?.response?.data?.detail || e?.message || 'Erro inesperado ao carregar status Figma/GitHub'
  } finally {
    carregandoStatus.value = false
  }
}

async function sincronizar() {
  sincronizando.value = true
  limparAlertas()
  try {
    const { data: payload } = await api.post(`${API_BASE}/sync`, montarPayload())
    if (!payload.success) throw new Error(payload.errors?.[0]?.message || 'Falha ao executar sincronização Figma/GitHub')
    resultadoSync.value = payload.data || payload
    mensagem.value = payload.data?.modo_degradado
      ? 'Sincronização degradada concluída com vínculos demonstrativos locais.'
      : 'Sincronização solicitada e retorno recebido em tela.'
    ultimaAcao.value = new Date().toLocaleString('pt-BR')
    await carregarStatus()
  } catch (e) {
    erro.value = e?.response?.data?.detail || e?.message || 'Erro inesperado ao sincronizar Figma/GitHub'
  } finally {
    sincronizando.value = false
  }
}

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

onMounted(carregarStatus)
</script>

<style scoped>
.figma-github { display: grid; gap: 1rem; padding: 28px 32px 40px; }
.cabecalho, .linha-painel { display: grid; gap: 1rem; align-items: start; }
.acoes-cabecalho { display: flex; gap: 0.5rem; justify-content: flex-start; }
.cards { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
.card, .painel { border: 1px solid var(--line); border-radius: 16px; padding: 1rem; background: rgba(255,255,255,0.02); }
.card span, .card strong { display: block; }
.card strong { font-size: 1.4rem; margin-top: 0.5rem; color: var(--accent); }
.formulario { display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-top: 1rem; }
.formulario label, .filtro { display: grid; gap: 0.25rem; font-weight: 600; color: var(--text); }
input, select, button { border: 1px solid var(--line); border-radius: 8px; padding: 0.65rem; background: rgba(255,255,255,0.04); color: var(--text); }
button { cursor: pointer; font-weight: 700; background: var(--accent); color: #111; border-color: var(--accent); }
button:disabled { cursor: not-allowed; opacity: 0.6; }
.checks { display: grid; gap: 0.4rem; align-content: end; }
.checks label { display: flex; gap: 0.4rem; align-items: center; font-weight: 500; }
.alerta { border-radius: 8px; padding: 0.75rem; }
.erro { border: 1px solid var(--red); color: var(--red); }
.sucesso { border: 1px solid var(--green); color: var(--green); }
.detalhes { display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
.detalhes div { border: 1px solid var(--line); border-radius: 8px; padding: 0.75rem; }
dt { font-weight: 700; }
dd { margin: 0.25rem 0 0; word-break: break-word; color: var(--muted); }
.json-retorno { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; padding: 0.75rem; }
.tabela-wrapper { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 980px; }
th, td { border-bottom: 1px solid var(--line); padding: 0.75rem; text-align: left; vertical-align: top; }
.badge { border: 1px solid var(--line); border-radius: 999px; padding: 0.2rem 0.55rem; }
.vazio { text-align: center; color: var(--muted); }
@media (min-width: 768px) { .cabecalho, .linha-painel { grid-template-columns: 1fr auto; } }
</style>
