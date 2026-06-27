<template>
  <div class="painel-page" data-testid="route-painel-integracao">
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Painel de Integrações</div>
        <div class="text-body-2 text-medium-emphasis">
          Histórico de tarefas enviadas ao Planner e notificações Teams com analítico filtrável.
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

    <!-- Cards de resumo clicáveis -->
    <v-row class="mb-4">
      <v-col
        v-for="card in cardsResumo"
        :key="card.id"
        cols="12"
        sm="6"
        md="3"
      >
        <v-card
          class="stat-card stat-card-interactive"
          variant="tonal"
          :color="card.cor"
          role="button"
          tabindex="0"
          :data-testid="`integracao-card-${card.id}`"
          @click="aplicarFiltroCard(card.filtros)"
          @keyup.enter="aplicarFiltroCard(card.filtros)"
          @keyup.space.prevent="aplicarFiltroCard(card.filtros)"
        >
          <v-card-text>
            <div class="d-flex align-center justify-space-between mb-1">
              <div class="text-caption">{{ card.titulo }}</div>
              <v-icon size="16" icon="mdi-filter-variant" />
            </div>
            <div class="text-h4 font-weight-bold">{{ card.valor }}</div>
            <div v-if="card.subtitulo" class="text-caption mt-1">{{ card.subtitulo }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Filtros analíticos -->
    <v-card class="mb-4 filter-card" variant="outlined">
      <v-card-text class="pa-3">
        <div class="filter-header mb-2">
          <div>
            <strong>Analítico de integrações</strong>
            <div class="text-caption text-medium-emphasis">
              Filtros por clique nos cards, dashboard ou seleção manual. {{ itensFiltrados.length }} de {{ itens.length }} eventos.
            </div>
          </div>
          <v-chip v-if="temFiltroAtivo" size="small" color="primary" variant="tonal">Filtro ativo</v-chip>
        </div>

        <v-row dense>
          <v-col cols="12" sm="6" md="2">
            <v-select
              v-model="filtros.tipo"
              :items="origemOptions"
              item-title="label"
              item-value="value"
              label="Origem"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              @update:model-value="sincronizarQuery"
            />
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <v-select
              v-model="filtros.status"
              :items="statusOptions"
              item-title="label"
              item-value="value"
              label="Status"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              @update:model-value="sincronizarQuery"
            />
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <v-text-field
              v-model="filtros.data"
              label="Data"
              type="date"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              @update:model-value="sincronizarQuery"
            />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <v-text-field
              v-model="filtros.correlation_id"
              label="Correlation ID"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              prepend-inner-icon="mdi-identifier"
              @update:model-value="sincronizarQuery"
            />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <v-text-field
              v-model="filtros.autor"
              label="Autor"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              @update:model-value="sincronizarQuery"
            />
          </v-col>
          <v-col cols="12">
            <v-text-field
              v-model="filtros.busca"
              label="Busca textual"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              prepend-inner-icon="mdi-magnify"
              placeholder="Título, mensagem, correlation_id..."
              @update:model-value="sincronizarQuery"
            />
          </v-col>
        </v-row>

        <div class="filter-actions mt-2">
          <v-btn
            variant="text"
            size="small"
            prepend-icon="mdi-filter-off"
            :disabled="!temFiltroAtivo"
            @click="limparFiltros"
          >
            Limpar filtros
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-alert v-if="!carregando && itens.length && !itensFiltrados.length" type="info" variant="tonal" class="mb-4">
      Nenhum evento encontrado para os filtros informados.
    </v-alert>

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
        <template #item.correlation_id="{ item }">
          <span
            v-if="item.correlation_id"
            class="text-caption correlation-link"
            role="button"
            tabindex="0"
            @click="filtrarPorCorrelation(item.correlation_id)"
            @keyup.enter="filtrarPorCorrelation(item.correlation_id)"
          >
            {{ item.correlation_id }}
          </span>
          <span v-else class="text-caption text-medium-emphasis">—</span>
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../services/api'
import {
  contarIntegracoesPorStatus,
  criarQueryFiltrosIntegracao,
  filtrarIntegracoes,
  normalizarFiltrosIntegracao,
  possuiFiltroAtivo,
} from '../utils/filtrosIntegracao'

const route = useRoute()
const router = useRouter()

const itens = ref([])
const carregando = ref(false)
const dialogAberto = ref(false)
const itemSelecionado = ref(null)
const snackbar = ref({ aberto: false, msg: '', cor: 'error' })

const configAberto = ref(undefined)
const configStatus = ref({ teams: false })
const configForm = ref({ teams_webhook_url: '' })
const salvando = ref(false)
const testando = ref(false)

const filtros = reactive(normalizarFiltrosIntegracao(route.query))

const origemOptions = [
  { label: 'Planner', value: 'planner' },
  { label: 'Teams', value: 'teams' },
]
const statusOptions = [
  { label: 'Sucesso', value: 'sucesso' },
  { label: 'Erro', value: 'erro' },
]

const headers = [
  { title: 'Data', key: 'criado_em', width: '150px' },
  { title: 'Origem', key: 'tipo', width: '100px' },
  { title: 'Status', key: 'status', width: '90px' },
  { title: 'Título', key: 'titulo' },
  { title: 'Autor', key: 'autor', width: '120px' },
  { title: 'Correlation ID', key: 'correlation_id', width: '140px' },
  { title: 'Tarefas', key: 'total', width: '70px', align: 'center' },
  { title: '', key: 'acoes', width: '50px', sortable: false },
]

const itensFiltrados = computed(() => filtrarIntegracoes(itens.value, filtros))
const temFiltroAtivo = computed(() => possuiFiltroAtivo(filtros))

const contagemStatus = computed(() => contarIntegracoesPorStatus(itens.value))

const totalTarefas = computed(() => itensFiltrados.value.reduce((s, i) => s + (i.total || 0), 0))
const totalTeams = computed(() => {
  return itens.value.filter((i) => {
    try {
      const det = typeof i.detalhes === 'string' ? JSON.parse(i.detalhes) : i.detalhes
      return det?.teams_notificado === true
    } catch (_) { return false }
  }).length
})

const ultimoStatus = computed(() => itens.value[0]?.status || '')
const ultimoEm = computed(() => (itens.value[0]?.criado_em ? formatarData(itens.value[0].criado_em) : ''))

const cardsResumo = computed(() => [
  {
    id: 'total',
    titulo: 'Total de Envios',
    valor: itensFiltrados.value.length,
    subtitulo: temFiltroAtivo.value ? `de ${itens.value.length} carregados` : 'Clique para limpar filtros',
    cor: 'primary',
    filtros: {},
  },
  {
    id: 'erros',
    titulo: 'Erros',
    valor: contagemStatus.value.erros,
    subtitulo: 'Filtrar falhas de integração',
    cor: 'error',
    filtros: { status: 'erro' },
  },
  {
    id: 'planner',
    titulo: 'Planner',
    valor: itens.value.filter((i) => i.tipo === 'planner').length,
    subtitulo: 'Filtrar origem Planner',
    cor: 'success',
    filtros: { tipo: 'planner' },
  },
  {
    id: 'teams',
    titulo: 'Teams',
    valor: totalTeams.value,
    subtitulo: 'Filtrar origem Teams',
    cor: 'info',
    filtros: { tipo: 'teams' },
  },
  {
    id: 'ultimo',
    titulo: 'Último Status',
    valor: ultimoStatus.value || '—',
    subtitulo: ultimoEm.value || 'Sem eventos',
    cor: ultimoStatus.value === 'erro' ? 'error' : ultimoStatus.value === 'sucesso' ? 'success' : 'grey',
    filtros: ultimoStatus.value ? { status: ultimoStatus.value } : {},
  },
])

watch(
  () => route.query,
  (query) => Object.assign(filtros, normalizarFiltrosIntegracao(query)),
)

function sincronizarQuery() {
  router.replace({ path: route.path, query: criarQueryFiltrosIntegracao(filtros) })
}

function limparFiltros() {
  Object.assign(filtros, { tipo: '', status: '', autor: '', correlation_id: '', data: '', busca: '' })
  sincronizarQuery()
}

function aplicarFiltroCard(novosFiltros) {
  if (!novosFiltros || !Object.keys(novosFiltros).length) {
    limparFiltros()
    return
  }
  Object.assign(filtros, normalizarFiltrosIntegracao(novosFiltros))
  sincronizarQuery()
}

function filtrarPorCorrelation(correlationId) {
  filtros.correlation_id = correlationId
  sincronizarQuery()
}

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
  gap: 12px;
  flex-wrap: wrap;
}
.stat-card {
  height: 100%;
}
.stat-card-interactive {
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stat-card-interactive:hover,
.stat-card-interactive:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}
.filter-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.filter-actions {
  display: flex;
  justify-content: flex-end;
}
.correlation-link {
  color: rgb(var(--v-theme-primary));
  cursor: pointer;
  text-decoration: underline dotted;
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
@media (max-width: 600px) {
  .filter-actions {
    justify-content: stretch;
  }
  .filter-actions :deep(.v-btn) {
    width: 100%;
  }
}
</style>
