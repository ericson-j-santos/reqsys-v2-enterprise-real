<template>
  <div class="painel-page">
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Painel de Integrações</div>
        <div class="text-body-2 text-medium-emphasis">
          Histórico de tarefas enviadas ao Planner e notificações Teams.
        </div>
      </div>
      <div class="page-actions">
        <v-btn variant="outlined" prepend-icon="mdi-refresh" :loading="carregando" @click="carregar">
          Atualizar
        </v-btn>
      </div>
    </div>

    <!-- Configuração Teams webhook -->
    <v-expansion-panels v-model="configAberto" class="mb-4">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <div class="d-flex align-center gap-2">
            <v-icon size="small" class="mr-2">mdi-cog-outline</v-icon>
            <span>Configuração de Webhooks</span>
            <v-chip v-if="configStatus.teams" size="x-small" color="success" variant="tonal" class="ml-2">Teams OK</v-chip>
            <v-chip v-else size="x-small" color="warning" variant="tonal" class="ml-2">Teams não configurado</v-chip>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-row dense class="mt-1">
            <v-col cols="12">
              <div class="text-caption text-medium-emphasis mb-3">
                Para notificações no Teams, crie um webhook via <strong>Teams → canal → (...) → Workflows → "Postar em um canal quando uma solicitação de webhook é recebida"</strong>, depois cole a URL abaixo.
              </div>
            </v-col>
            <v-col cols="12" md="8">
              <v-text-field
                v-model="configForm.teams_webhook_url"
                label="URL do Webhook Teams (Workflows)"
                density="compact"
                variant="outlined"
                hide-details="auto"
                placeholder="https://prod-XX.westus.logic.azure.com/..."
                prepend-inner-icon="mdi-microsoft-teams"
                clearable
              />
            </v-col>
            <v-col cols="12" md="4" class="d-flex align-center gap-2">
              <v-btn
                color="primary"
                variant="tonal"
                size="small"
                :loading="salvando"
                @click="salvarConfig"
                prepend-icon="mdi-content-save-outline"
              >
                Salvar
              </v-btn>
              <v-btn
                color="info"
                variant="tonal"
                size="small"
                :loading="testando"
                :disabled="!configForm.teams_webhook_url"
                @click="testarTeams"
                prepend-icon="mdi-send-check-outline"
              >
                Testar
              </v-btn>
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Cards de resumo -->
    <v-row class="mb-4">
      <v-col cols="12" sm="6" md="3">
        <v-card class="stat-card" variant="tonal" color="primary">
          <v-card-text>
            <div class="text-caption mb-1">Total de Envios</div>
            <div class="text-h4 font-weight-bold">{{ totalEnvios }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card class="stat-card" variant="tonal" color="success">
          <v-card-text>
            <div class="text-caption mb-1">Tarefas Criadas</div>
            <div class="text-h4 font-weight-bold">{{ totalTarefas }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card class="stat-card" variant="tonal" color="info">
          <v-card-text>
            <div class="text-caption mb-1">Teams Notificados</div>
            <div class="text-h4 font-weight-bold">{{ totalTeams }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card class="stat-card" variant="tonal" :color="ultimoStatus === 'ok' ? 'success' : ultimoStatus ? 'error' : 'grey'">
          <v-card-text>
            <div class="text-caption mb-1">Último Status</div>
            <div class="text-h5 font-weight-bold">{{ ultimoStatus || '—' }}</div>
            <div class="text-caption mt-1">{{ ultimoEm }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Filtros -->
    <v-card class="mb-4" variant="outlined">
      <v-card-text class="pa-3">
        <v-row dense>
          <v-col cols="12" sm="4">
            <v-select
              v-model="filtroTipo"
              :items="['Todos', 'planner', 'teams']"
              label="Tipo"
              density="compact"
              variant="outlined"
              hide-details
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-select
              v-model="filtroStatus"
              :items="['Todos', 'sucesso', 'erro']"
              label="Status"
              density="compact"
              variant="outlined"
              hide-details
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field
              v-model="filtroAutor"
              label="Autor"
              density="compact"
              variant="outlined"
              hide-details
              clearable
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Tabela -->
    <v-card variant="outlined">
      <v-data-table
        :headers="headers"
        :items="itensFiltrados"
        :loading="carregando"
        density="compact"
        class="painel-tabela"
        no-data-text="Nenhum evento encontrado."
      >
        <!-- eslint-disable-next-line vue/valid-v-slot -->
        <template #item.criado_em="{ item }">
          <span class="text-caption">{{ formatarData(item.criado_em) }}</span>
        </template>
        <!-- eslint-disable-next-line vue/valid-v-slot -->
        <template #item.tipo="{ item }">
          <v-chip size="x-small" :color="item.tipo === 'planner' ? 'primary' : 'info'" variant="tonal">
            {{ item.tipo === 'planner' ? 'Planner' : item.tipo === 'teams' ? 'Teams' : item.tipo }}
          </v-chip>
        </template>
        <!-- eslint-disable-next-line vue/valid-v-slot -->
        <template #item.status="{ item }">
          <v-chip
            size="x-small"
            :color="item.status === 'sucesso' ? 'success' : item.status === 'erro' ? 'error' : 'grey'"
            variant="tonal"
          >
            {{ item.status }}
          </v-chip>
        </template>
        <!-- eslint-disable-next-line vue/valid-v-slot -->
        <template #item.total="{ item }">
          <span>{{ item.total || '—' }}</span>
        </template>
        <!-- eslint-disable-next-line vue/valid-v-slot -->
        <template #item.acoes="{ item }">
          <v-btn icon="mdi-eye" size="x-small" variant="text" @click="abrirDetalhes(item)" />
        </template>
      </v-data-table>
    </v-card>

    <!-- Dialog de detalhes -->
    <v-dialog v-model="dialogAberto" max-width="700">
      <v-card v-if="itemSelecionado">
        <v-card-title class="d-flex align-center justify-space-between">
          <span>Detalhes do evento #{{ itemSelecionado.id }}</span>
          <v-btn icon="mdi-close" variant="text" @click="dialogAberto = false" />
        </v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item subtitle="Tipo" :title="itemSelecionado.tipo" />
            <v-list-item subtitle="Status" :title="itemSelecionado.status" />
            <v-list-item subtitle="Título" :title="itemSelecionado.titulo || '—'" />
            <v-list-item subtitle="Autor" :title="itemSelecionado.autor || '—'" />
            <v-list-item subtitle="Tarefas" :title="String(itemSelecionado.total || 0)" />
            <v-list-item v-if="itemSelecionado.mensagem" subtitle="Mensagem" :title="itemSelecionado.mensagem" />
            <v-list-item v-if="itemSelecionado.correlation_id" subtitle="Correlation ID" :title="itemSelecionado.correlation_id" />
          </v-list>
          <div v-if="itemSelecionado.detalhes && itemSelecionado.detalhes !== '{}'" class="mt-3">
            <div class="text-caption text-medium-emphasis mb-1">Resposta do Flow</div>
            <pre class="detalhes-json">{{ formatarDetalhes(itemSelecionado.detalhes) }}</pre>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar.aberto" :color="snackbar.cor" timeout="4000">
      {{ snackbar.msg }}
    </v-snackbar>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../services/api'

const itens = ref([])
const carregando = ref(false)
const filtroTipo = ref('Todos')
const filtroStatus = ref('Todos')
const filtroAutor = ref('')
const dialogAberto = ref(false)
const itemSelecionado = ref(null)
const snackbar = ref({ aberto: false, msg: '', cor: 'error' })

const configAberto = ref(undefined)
const configStatus = ref({ teams: false })
const configForm = ref({ teams_webhook_url: '' })
const salvando = ref(false)
const testando = ref(false)

const headers = [
  { title: 'Data', key: 'criado_em', width: '160px' },
  { title: 'Tipo', key: 'tipo', width: '110px' },
  { title: 'Status', key: 'status', width: '90px' },
  { title: 'Título', key: 'titulo' },
  { title: 'Autor', key: 'autor', width: '140px' },
  { title: 'Tarefas', key: 'total', width: '80px', align: 'center' },
  { title: '', key: 'acoes', width: '50px', sortable: false },
]

const itensFiltrados = computed(() => {
  return itens.value.filter((i) => {
    if (filtroTipo.value !== 'Todos' && i.tipo !== filtroTipo.value) return false
    if (filtroStatus.value !== 'Todos' && i.status !== filtroStatus.value) return false
    if (filtroAutor.value && !i.autor?.toLowerCase().includes(filtroAutor.value.toLowerCase())) return false
    return true
  })
})

const totalEnvios = computed(() => itensFiltrados.value.length)
const totalTarefas = computed(() => itensFiltrados.value.reduce((s, i) => s + (i.total || 0), 0))
const totalTeams = computed(() => {
  return itensFiltrados.value.filter((i) => {
    try {
      const det = typeof i.detalhes === 'string' ? JSON.parse(i.detalhes) : i.detalhes
      return det?.teams_notificado === true
    } catch (_) { return false }
  }).length
})
const ultimoStatus = computed(() => itens.value[0]?.status || '')
const ultimoEm = computed(() => (itens.value[0]?.criado_em ? formatarData(itens.value[0].criado_em) : ''))

function formatarData(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function formatarDetalhes(detalhes) {
  try {
    const obj = typeof detalhes === 'string' ? JSON.parse(detalhes) : detalhes
    return JSON.stringify(obj, null, 2)
  } catch (_) {
    return detalhes
  }
}

function abrirDetalhes(item) {
  itemSelecionado.value = item
  dialogAberto.value = true
}

async function carregarConfig() {
  try {
    const resp = await api.get('/v1/hub-lowcode/planner/webhook-config')
    const data = resp.data?.data || {}
    configStatus.value.teams = data.teams_configurado || false
  } catch (_) {}
}

async function salvarConfig() {
  salvando.value = true
  try {
    await api.put('/v1/hub-lowcode/planner/webhook-config', {
      teams_webhook_url: configForm.value.teams_webhook_url || '',
    })
    await carregarConfig()
    snackbar.value = { aberto: true, msg: 'Configuração salva com sucesso.', cor: 'success' }
  } catch (e) {
    snackbar.value = { aberto: true, msg: 'Erro ao salvar: ' + (e?.response?.data?.detail || e.message), cor: 'error' }
  } finally {
    salvando.value = false
  }
}

async function testarTeams() {
  testando.value = true
  try {
    const resp = await api.post('/v1/hub-lowcode/teams/testar-webhook', {
      teams_webhook_url: configForm.value.teams_webhook_url || null,
    })
    const ok = resp.data?.data?.ok
    snackbar.value = {
      aberto: true,
      msg: ok ? 'Mensagem de teste enviada ao Teams!' : ('Erro: ' + (resp.data?.data?.erro || 'desconhecido')),
      cor: ok ? 'success' : 'error',
    }
  } catch (e) {
    snackbar.value = { aberto: true, msg: 'Erro ao testar: ' + (e?.response?.data?.detail || e.message), cor: 'error' }
  } finally {
    testando.value = false
  }
}

async function carregar() {
  carregando.value = true
  try {
    const resp = await api.get('/v1/hub-lowcode/integracoes/historico?limit=100')
    itens.value = resp.data?.data?.eventos || []
  } catch (e) {
    snackbar.value = { aberto: true, msg: 'Erro ao carregar histórico: ' + (e?.response?.data?.detail || e.message), cor: 'error' }
  } finally {
    carregando.value = false
  }
}

onMounted(async () => {
  await carregarConfig()
  await carregar()
})
</script>

<style scoped>
.painel-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.stat-card {
  height: 100%;
}
.detalhes-json {
  font-size: 12px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
