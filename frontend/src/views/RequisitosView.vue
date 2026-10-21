<template>
  <section class="page" data-testid="route-requisitos">
    <div class="page-header">
      <div>
        <h1>Requisitos</h1>
        <p class="muted requisitos-subtitle">
          Cadastre, acompanhe e priorize solicitações com contexto funcional e operacional.
        </p>
      </div>
      <div class="header-actions">
        <v-tooltip text="Recarrega a listagem atual de requisitos" location="top" aria-label="Recarrega a listagem atual de requisitos">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="outlined" prepend-icon="mdi-refresh" :loading="store.carregando" @click="carregar">
              Atualizar
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Abre o formulário para registrar uma nova solicitação" location="top" aria-label="Abre o formulário para registrar uma nova solicitação">
          <template #activator="{ props }">
            <v-btn v-bind="props" color="amber" prepend-icon="mdi-plus" @click="dialog = true">
              Novo requisito
            </v-btn>
          </template>
        </v-tooltip>
      </div>
    </div>

    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-card class="table-card summary-card">
          <div class="muted">Total em lista</div>
          <div class="summary-value">{{ requisitosFiltrados.length }}</div>
          <div v-if="temFiltroAtivo" class="muted summary-filter">de {{ store.itens.length }} requisitos carregados</div>
        </v-card>
      </v-col>
      <v-col cols="12" md="8">
        <v-alert type="info" variant="tonal">
          Use a lista para visão rápida e o formulário para registrar novas demandas com urgência, área e sistema de origem.
        </v-alert>
      </v-col>
    </v-row>

    <v-card class="table-card filter-card mb-4" elevation="0">
      <div class="filter-header">
        <div>
          <strong>Analítico de requisitos</strong>
          <div class="muted filter-subtitle">Filtros aplicados por clique no painel ou seleção manual. Clique em uma linha para ver detalhes.</div>
        </div>
        <v-chip v-if="temFiltroAtivo" size="small" color="amber" variant="tonal">Filtro ativo</v-chip>
      </div>

      <v-row class="mt-1">
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="filtros.status"
            label="Situação"
            variant="outlined"
            density="compact"
            clearable
            :items="statusOptions"
            item-title="label"
            item-value="value"
            @update:model-value="sincronizarQuery"
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="filtros.urgencia"
            label="Urgência"
            variant="outlined"
            density="compact"
            clearable
            :items="urgenciaOptions"
            item-title="label"
            item-value="value"
            @update:model-value="sincronizarQuery"
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filtros.area" label="Área" variant="outlined" density="compact" clearable @update:model-value="sincronizarQuery" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field
            v-model="filtros.busca"
            label="Busca"
            variant="outlined"
            density="compact"
            clearable
            prepend-inner-icon="mdi-magnify"
            @update:model-value="sincronizarQuery"
          />
        </v-col>
      </v-row>

      <div class="filter-actions">
        <v-btn variant="text" size="small" prepend-icon="mdi-filter-off" :disabled="!temFiltroAtivo" @click="limparFiltros">
          Limpar filtros
        </v-btn>
      </div>
    </v-card>

    <v-alert v-if="store.erro" type="error" variant="tonal" class="mb-4">
      {{ store.erro }}
    </v-alert>

    <v-alert v-if="!store.carregando && requisitosFiltrados.length === 0" type="warning" variant="tonal" class="mb-4">
      Nenhum requisito encontrado para os filtros informados.
    </v-alert>

    <v-skeleton-loader v-if="store.carregando" type="table" />
    <v-data-table
      v-else
      :headers="headers"
      :items="requisitosFiltrados"
      item-value="id"
      class="table-card requisitos-table requisitos-table-clicavel"
      @click:row="abrirDetalhe"
    >
      <template v-slot:[`item.status`]="{ item }">
        <v-tooltip text="Situação atual do requisito no fluxo operacional" location="top" aria-label="Situação atual do requisito no fluxo operacional">
          <template #activator="{ props }">
            <v-chip v-bind="props" size="small" :color="corStatus(item.status)">{{ item.status }}</v-chip>
          </template>
        </v-tooltip>
      </template>
    </v-data-table>

    <v-dialog v-model="detalheDialog" width="640">
      <v-card v-if="detalhe">
        <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
          <span>{{ detalhe.titulo }}</span>
          <v-chip size="small" :color="corStatus(detalhe.status)">{{ detalhe.status }}</v-chip>
        </v-card-title>
        <v-card-text>
          <div class="muted mb-3">{{ detalhe.codigo }}</div>
          <p class="detalhe-descricao">{{ detalhe.descricao }}</p>
          <v-row class="mt-2">
            <v-col cols="6" sm="4"><div class="muted">Urgência</div><div>{{ detalhe.urgencia }}</div></v-col>
            <v-col cols="6" sm="4"><div class="muted">Área</div><div>{{ detalhe.area }}</div></v-col>
            <v-col cols="6" sm="4"><div class="muted">Sistema</div><div>{{ detalhe.sistema }}</div></v-col>
            <v-col cols="6" sm="4"><div class="muted">Solicitante</div><div>{{ detalhe.solicitante }}</div></v-col>
            <v-col cols="6" sm="4">
              <div class="muted">Impacto regulatório</div>
              <div>{{ detalhe.impacto_regulatorio ? 'Sim' : 'Não' }}</div>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="detalheDialog = false">Fechar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="dialog" width="760">
      <v-card>
        <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
          <span>Nova solicitação de requisito</span>
          <v-chip size="small" color="amber" variant="tonal">Cadastro guiado</v-chip>
        </v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <v-tooltip text="Resumo curto e objetivo do requisito" location="top" aria-label="Resumo curto e objetivo do requisito">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-text-field v-model="form.titulo" label="Título" variant="outlined" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
            <v-col cols="12" md="6">
              <v-tooltip text="Prioridade usada na triagem e ordenação do backlog" location="top" aria-label="Prioridade usada na triagem e ordenação do backlog">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-select v-model="form.urgencia" label="Urgência" variant="outlined" :items="['baixa', 'media', 'alta', 'critica']" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
          </v-row>

          <v-tooltip text="Explique a necessidade de negócio e o impacto esperado" location="top" aria-label="Explique a necessidade de negócio e o impacto esperado">
            <template #activator="{ props }">
              <div v-bind="props">
                <v-textarea v-model="form.descricao" label="Descrição" variant="outlined" rows="4" />
              </div>
            </template>
          </v-tooltip>

          <v-row>
            <v-col cols="12" md="4">
              <v-text-field v-model="form.area" label="Área" variant="outlined" />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field v-model="form.sistema" label="Sistema" variant="outlined" />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field v-model="form.solicitante" label="Solicitante" variant="outlined" />
            </v-col>
          </v-row>

          <v-expand-transition>
            <v-alert v-if="ia.erro" type="warning" variant="tonal" class="mt-2" closable @click:close="ia.erro = ''">
              {{ ia.erro }}
            </v-alert>
          </v-expand-transition>
          <v-expand-transition>
            <v-alert v-if="ia.justificativa" type="success" variant="tonal" class="mt-2" icon="mdi-robot">
              <strong>Urgência sugerida:</strong> {{ ia.urgenciaSugerida }}
              <br />{{ ia.justificativa }}
            </v-alert>
          </v-expand-transition>
        </v-card-text>

        <v-card-actions>
          <v-btn color="purple" variant="tonal" prepend-icon="mdi-robot" :loading="ia.carregando" :disabled="!form.titulo" @click="assistenteIA">
            Assistente IA
          </v-btn>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancelar</v-btn>
          <v-btn color="amber" :loading="salvando" @click="salvar">Salvar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup>
import { computed, reactive, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRequisitosStore } from '../stores/requisitos'
import { api } from '../services/api'
import { criarQueryFiltrosRequisitos, filtrarRequisitos, normalizarFiltrosRequisitos, possuiFiltroAtivo } from '../utils/filtrosRequisitos'

const store = useRequisitosStore()
const route = useRoute()
const router = useRouter()
const dialog = ref(String(route.query.acao || '') === 'novo')
const salvando = ref(false)
const detalheDialog = ref(false)
const detalhe = ref(null)
const filtros = reactive(normalizarFiltrosRequisitos(route.query))

const form = reactive({ titulo: '', descricao: '', urgencia: 'media', area: '', sistema: '', solicitante: '' })
const ia = reactive({ carregando: false, erro: '', justificativa: '', urgenciaSugerida: '' })

const URGENCIAS_VALIDAS = new Set(['baixa', 'media', 'alta', 'critica'])
let consultaIAId = 0

function invalidarConsultaIA() {
  consultaIAId += 1
  ia.carregando = false
  ia.erro = ''
  ia.justificativa = ''
  ia.urgenciaSugerida = ''
}

watch(dialog, (aberto) => {
  if (!aberto) invalidarConsultaIA()
}, { flush: 'sync' })

onBeforeUnmount(invalidarConsultaIA)

const headers = [
  { title: 'Código', key: 'codigo' },
  { title: 'Título', key: 'titulo' },
  { title: 'Situação', key: 'status' },
  { title: 'Urgência', key: 'urgencia' },
  { title: 'Área', key: 'area' },
]

const statusOptions = [
  { label: 'Recebido', value: 'recebido' },
  { label: 'Em análise', value: 'em_analise' },
  { label: 'Aprovado', value: 'aprovado' },
  { label: 'Rejeitado', value: 'rejeitado' },
]

const urgenciaOptions = [
  { label: 'Baixa', value: 'baixa' },
  { label: 'Média', value: 'media' },
  { label: 'Alta', value: 'alta' },
  { label: 'Crítica', value: 'critica' },
]

const requisitosFiltrados = computed(() => filtrarRequisitos(store.itens, filtros))
const temFiltroAtivo = computed(() => possuiFiltroAtivo(filtros))

onMounted(carregar)

watch(
  () => route.query,
  (query) => {
    Object.assign(filtros, normalizarFiltrosRequisitos(query))
    if (String(query.acao || '') === 'novo') dialog.value = true
  },
)

function carregar() { store.listar() }
function sincronizarQuery() { router.replace({ path: route.path, query: criarQueryFiltrosRequisitos(filtros) }) }
function limparFiltros() {
  Object.assign(filtros, { status: '', urgencia: '', area: '', busca: '' })
  sincronizarQuery()
}
function corStatus(status) { return ({ recebido: 'blue', em_analise: 'orange', aprovado: 'green', rejeitado: 'red' })[status] || 'grey' }
function abrirDetalhe(_event, { item } = {}) {
  detalhe.value = item?.raw ?? item ?? null
  if (detalhe.value) detalheDialog.value = true
}

async function salvar() {
  salvando.value = true
  invalidarConsultaIA()
  try {
    await store.criar({ ...form })
    dialog.value = false
  } finally {
    salvando.value = false
  }
}

async function assistenteIA() {
  if (ia.carregando || salvando.value || !dialog.value) return

  const requestId = ++consultaIAId
  const entrada = { ...form }
  ia.carregando = true
  ia.erro = ''
  ia.justificativa = ''
  ia.urgenciaSugerida = ''

  try {
    const [resDescricao, resUrgencia] = await Promise.allSettled([
      api.post('/v1/ia/sugerir-descricao', {
        titulo: entrada.titulo,
        area: entrada.area,
        sistema: entrada.sistema,
      }),
      api.post('/v1/ia/classificar-urgencia', {
        titulo: entrada.titulo,
        descricao: entrada.descricao || entrada.titulo,
      }),
    ])

    if (requestId !== consultaIAId || !dialog.value) return

    const contextoPreservado = ['titulo', 'descricao', 'area', 'sistema']
      .every((campo) => form[campo] === entrada[campo])
    if (!contextoPreservado) {
      ia.erro = 'Os dados foram alterados durante a consulta. As sugestões foram descartadas para preservar suas alterações.'
      return
    }

    const urgenciaPreservada = form.urgencia === entrada.urgencia
    const avisos = []

    const descricaoEnvelope = resDescricao.status === 'fulfilled'
      ? resDescricao.value.data
      : null
    const sugestao = descricaoEnvelope?.data?.descricao_sugerida
    if (
      descricaoEnvelope?.success === true
      && typeof sugestao === 'string'
      && sugestao.trim()
    ) {
      form.descricao = sugestao.trim()
    } else {
      avisos.push('Não foi possível sugerir uma descrição. A descrição preenchida foi mantida.')
    }

    const urgenciaEnvelope = resUrgencia.status === 'fulfilled'
      ? resUrgencia.value.data
      : null
    const dados = urgenciaEnvelope?.data
    const classificacaoValida = urgenciaEnvelope?.success === true
      && URGENCIAS_VALIDAS.has(dados?.urgencia)
      && typeof dados?.justificativa === 'string'
      && dados.justificativa.trim().length > 0

    if (!classificacaoValida) {
      avisos.push('Não foi possível obter uma classificação válida de urgência. A urgência preenchida foi mantida; revise-a manualmente.')
    } else if (!urgenciaPreservada) {
      avisos.push('A urgência foi alterada durante a consulta e sua escolha foi mantida.')
    } else {
      form.urgencia = dados.urgencia
      ia.urgenciaSugerida = dados.urgencia
      ia.justificativa = dados.justificativa.trim()
    }

    ia.erro = avisos.join(' ')
  } catch {
    if (requestId === consultaIAId && dialog.value) {
      ia.erro = 'Não foi possível concluir a consulta ao Assistente IA. Os campos preenchidos foram mantidos.'
    }
  } finally {
    if (requestId === consultaIAId) ia.carregando = false
  }
}
</script>

<style scoped>
.requisitos-subtitle { max-width: 58ch; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.summary-card { padding: var(--space-lg); }
.summary-value { font-size: var(--font-size-display); font-weight: 800; color: var(--accent); }
.summary-filter, .filter-subtitle { font-size: var(--font-size-sm); }
.filter-card { padding: var(--space-lg); }
.filter-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.filter-actions { display: flex; justify-content: flex-end; }
.requisitos-table-clicavel :deep(tbody tr) { cursor: pointer; }
.requisitos-table-clicavel :deep(tbody tr:hover) { background: rgba(var(--v-theme-on-surface), 0.06); }
.detalhe-descricao { white-space: pre-wrap; }
@media (max-width: 720px) {
  .header-actions, .filter-actions { justify-content: stretch; }
  .header-actions :deep(.v-btn), .filter-actions :deep(.v-btn) { width: 100%; }
  .requisitos-table :deep(table) { min-width: 760px; }
}
</style>
