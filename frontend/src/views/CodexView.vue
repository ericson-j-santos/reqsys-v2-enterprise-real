<template>
  <section class="page" data-testid="route-codex">
    <PageHeader
      title="Codex Governado"
      subtitle="Análise de código com LLM local, Groq/Llama ou mock, com JWT, rate limit, auditoria e correlation_id."
      :chip="statusLabel"
      :chip-color="statusColor"
      chip-tooltip="Status do serviço Codex governado"
    >
      <template #actions>
        <v-tooltip text="Verifica conectividade com o backend Codex" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-heart-pulse"
              :loading="carregandoStatus"
              data-testid="btn-status-codex"
              @click="carregarStatus"
            >
              Status
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Abre o Codex Online (GitHub Pages)" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-open-in-new"
              href="https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/"
              target="_blank"
              rel="noopener"
            >
              Online
            </v-btn>
          </template>
        </v-tooltip>
      </template>
    </PageHeader>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" data-testid="alerta-erro">
      {{ erro }}
    </v-alert>

    <v-row>
      <v-col cols="12" md="7">
        <v-card class="table-card">
          <v-card-title class="py-3 px-4">Análise governada</v-card-title>
          <v-divider />
          <v-card-text>
            <v-select
              v-model="provider"
              :items="providers"
              label="Provider"
              density="compact"
              data-testid="select-provider"
            />
            <v-textarea
              v-model="contexto"
              label="Contexto técnico"
              rows="2"
              auto-grow
              placeholder="Repositório, branch, workflow, requisito..."
              data-testid="input-contexto"
            />
            <v-textarea
              v-model="entrada"
              label="Código, log ou requisito"
              rows="5"
              auto-grow
              placeholder="Cole conteúdo sem credenciais ou dados pessoais..."
              data-testid="input-entrada"
            />
            <div class="d-flex gap-2 flex-wrap mt-2">
              <v-btn
                color="primary"
                prepend-icon="mdi-robot"
                :loading="analisando"
                data-testid="btn-analisar"
                @click="analisar"
              >
                Analisar
              </v-btn>
              <v-btn
                variant="outlined"
                prepend-icon="mdi-code-json"
                data-testid="btn-payload"
                @click="gerarPayload"
              >
                Payload ReqSys
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="5">
        <v-card class="table-card h-100">
          <v-card-title class="py-3 px-4">Guard rails</v-card-title>
          <v-divider />
          <v-card-text>
            <v-skeleton-loader v-if="carregandoStatus && !status" type="list-item@4" />
            <v-list v-else density="compact">
              <v-list-item
                v-for="item in guardRails"
                :key="item"
                prepend-icon="mdi-shield-check"
              >
                {{ item }}
              </v-list-item>
            </v-list>
            <v-alert type="info" variant="tonal" density="compact" class="mt-3">
              VS Code local: use Continue + Ollama.
              Veja <code>docs/runbooks/codex-vscode-local-inicio-rapido.md</code>.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="table-card mt-4">
      <v-card-title class="py-3 px-4">Resultado</v-card-title>
      <v-divider />
      <v-card-text>
        <pre class="resultado" data-testid="resultado-codex">{{ resultado || 'Aguardando análise.' }}</pre>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../services/api'

const providers = ['mock', 'ollama', 'ollama_gateway', 'openai', 'claude', 'groq']
const provider = ref('mock')
const contexto = ref('')
const entrada = ref('')
const resultado = ref('')
const erro = ref('')
const status = ref(null)
const carregandoStatus = ref(false)
const analisando = ref(false)

const guardRails = computed(() => status.value?.guard_rails || [
  'jwt', 'rate_limit', 'auditoria', 'bloqueio_conteudo_sensivel', 'correlation_id',
])

const statusLabel = computed(() => (status.value ? 'Online' : 'Verificando'))
const statusColor = computed(() => (status.value ? 'success' : 'warning'))

function cid() {
  return `codex-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

async function carregarStatus() {
  carregandoStatus.value = true
  erro.value = ''
  try {
    const { data } = await api.get('/v1/codex/status')
    status.value = data.data
  } catch (e) {
    erro.value = e?.response?.data?.detail?.motivo || e?.message || 'Falha ao carregar status'
    status.value = null
  } finally {
    carregandoStatus.value = false
  }
}

async function analisar() {
  if (!contexto.value.trim() && !entrada.value.trim()) {
    erro.value = 'Informe contexto ou entrada para análise.'
    return
  }
  analisando.value = true
  erro.value = ''
  resultado.value = 'Processando...'
  try {
    const { data } = await api.post('/v1/codex/analyze', {
      provider: provider.value,
      contexto: contexto.value || 'Análise Codex ReqSys',
      entrada: entrada.value || contexto.value,
      correlation_id: cid(),
      publicar_no_reqsys: false,
    })
    resultado.value = JSON.stringify(data.data, null, 2)
  } catch (e) {
    const detail = e?.response?.data?.detail
    erro.value = typeof detail === 'object' ? JSON.stringify(detail) : (detail || e?.message || 'Erro na análise')
    resultado.value = ''
  } finally {
    analisando.value = false
  }
}

function gerarPayload() {
  const id = cid()
  resultado.value = JSON.stringify({
    correlation_id: id,
    sistema: 'ReqSys',
    modulo: 'Codex Governado',
    ambiente: 'local',
    tipo: 'demanda_tecnica',
    descricao: contexto.value.trim(),
    entrada: entrada.value.trim().slice(0, 4000),
    guard_rails: guardRails.value,
    status: 'rascunho_validacao',
  }, null, 2)
}

onMounted(carregarStatus)
</script>

<style scoped>
.resultado {
  white-space: pre-wrap;
  background: rgba(8, 13, 28, 0.6);
  border: 1px solid rgba(43, 54, 95, 0.5);
  border-radius: 12px;
  padding: 14px;
  min-height: 160px;
  overflow: auto;
  font-size: 0.85rem;
}
.gap-2 { gap: 8px; }
</style>
