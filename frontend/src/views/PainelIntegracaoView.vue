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
              :items="['Todos', 'planner_task', 'teams_notification']"
              label="Tipo"
              density="compact"
              variant="outlined"
              hide-details
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-select
              v-model="filtroStatus"
              :items="['Todos', 'ok', 'erro', 'skip']"
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
        <template #item.criado_em="{ item }">
          <span class="text-caption">{{ formatarData(item.criado_em) }}</span>
        </template>
        <template #item.tipo="{ item }">
          <v-chip size="x-small" :color="item.tipo === 'planner_task' ? 'primary' : 'info'" variant="tonal">
            {{ item.tipo === 'planner_task' ? 'Planner' : 'Teams' }}
          </v-chip>
        </template>
        <template #item.status="{ item }">
          <v-chip
            size="x-small"
            :color="item.status === 'ok' ? 'success' : item.status === 'erro' ? 'error' : 'grey'"
            variant="tonal"
          >
            {{ item.status }}
          </v-chip>
        </template>
        <template #item.total="{ item }">
          <span>{{ item.total || '—' }}</span>
        </template>
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
          <div v-if="itemSelecionado.detalhes" class="mt-3">
            <div class="text-caption text-medium-emphasis mb-1">Resposta do Flow</div>
            <pre class="detalhes-json">{{ JSON.stringify(itemSelecionado.detalhes, null, 2) }}</pre>
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
    const det = i.detalhes
    return det && typeof det === 'object' && det.teams_notificado
  }).length
})
const ultimoStatus = computed(() => itens.value[0]?.status || '')
const ultimoEm = computed(() => (itens.value[0]?.criado_em ? formatarData(itens.value[0].criado_em) : ''))

function formatarData(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function abrirDetalhes(item) {
  itemSelecionado.value = item
  dialogAberto.value = true
}

async function carregar() {
  carregando.value = true
  try {
    const resp = await api.get('/v1/hub-lowcode/integracoes/historico?limit=100')
    itens.value = resp.data?.data || []
  } catch (e) {
    snackbar.value = { aberto: true, msg: 'Erro ao carregar histórico: ' + (e?.response?.data?.detail || e.message), cor: 'error' }
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)
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
