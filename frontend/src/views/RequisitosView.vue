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
        <v-tooltip text="Recarrega a listagem atual de requisitos" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="outlined" prepend-icon="mdi-refresh" :loading="store.carregando" @click="carregar">
              Atualizar
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Abre o formulário para registrar uma nova solicitação" location="top">
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
          <div class="muted filter-subtitle">Filtros aplicados por clique no dashboard ou seleção manual.</div>
        </div>
        <v-chip v-if="temFiltroAtivo" size="small" color="amber" variant="tonal">Filtro ativo</v-chip>
      </div>

      <v-row class="mt-1">
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="filtros.status"
            label="Status"
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
    <v-data-table v-else :headers="headers" :items="requisitosFiltrados" item-value="id" class="table-card requisitos-table">
      <template v-slot:[`item.status`]="{ item }">
        <v-tooltip text="Situação atual do requisito no fluxo operacional" location="top">
          <template #activator="{ props }">
            <v-chip v-bind="props" size="small" :color="corStatus(item.status)">{{ item.status }}</v-chip>
          </template>
        </v-tooltip>
      </template>
    </v-data-table>

    <v-dialog v-model="dialog" width="760">
      <v-card>
        <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
          <span>Nova solicitação de requisito</span>
          <v-chip size="small" color="amber" variant="tonal">Cadastro guiado</v-chip>
        </v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <v-tooltip text="Resumo curto e objetivo do requisito" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-text-field v-model="form.titulo" label="Título" variant="outlined" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
            <v-col cols="12" md="6">
              <v-tooltip text="Prioridade usada na triagem e ordenação do backlog" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-select v-model="form.urgencia" label="Urgência" variant="outlined" :items="['baixa', 'media', 'alta', 'critica']" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
          </v-row>

          <v-tooltip text="Explique a necessidade de negócio e o impacto esperado" location="top">
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
import { computed, reactive, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRequisitosStore } from '../stores/requisitos'
import axios from 'axios'
import { criarQueryFiltrosRequisitos, filtrarRequisitos, normalizarFiltrosRequisitos, possuiFiltroAtivo } from '../utils/filtrosRequisitos'

const store = useRequisitosStore()
const route = useRoute()
const router = useRouter()
const dialog = ref(false)
const salvando = ref(false)
const filtros = reactive(normalizarFiltrosRequisitos(route.query))

const form = reactive({ titulo: '', descricao: '', urgencia: 'media', area: '', sistema: '', solicitante: '' })
const ia = reactive({ carregando: false, erro: '', justificativa: '', urgenciaSugerida: '' })

const headers = [
  { title: 'Código', key: 'codigo' },
  { title: 'Título', key: 'titulo' },
  { title: 'Status', key: 'status' },
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
  (query) => Object.assign(filtros, normalizarFiltrosRequisitos(query)),
)

function carregar() { store.listar() }
function sincronizarQuery() { router.replace({ path: route.path, query: criarQueryFiltrosRequisitos(filtros) }) }
function limparFiltros() {
  Object.assign(filtros, { status: '', urgencia: '', area: '', busca: '' })
  sincronizarQuery()
}
function corStatus(status) { return ({ recebido: 'blue', em_analise: 'orange', aprovado: 'green', rejeitado: 'red' })[status] || 'grey' }

async function salvar() {
  salvando.value = true
  try {
    await store.criar({ ...form })
    dialog.value = false
  } finally {
    salvando.value = false
  }
}

async function assistenteIA() {
  ia.carregando = true
  ia.erro = ''
  ia.justificativa = ''
  ia.urgenciaSugerida = ''
  try {
    const base = import.meta.env.VITE_API_URL || '/api'
    const [resDescricao, resUrgencia] = await Promise.allSettled([
      axios.post(`${base}/v1/ia/sugerir-descricao`, { titulo: form.titulo, area: form.area, sistema: form.sistema }),
      axios.post(`${base}/v1/ia/classificar-urgencia`, { titulo: form.titulo, descricao: form.descricao || form.titulo }),
    ])
    if (resDescricao.status === 'fulfilled') {
      const sugestao = resDescricao.value.data?.data?.descricao_sugerida
      if (sugestao) form.descricao = sugestao
    } else {
      ia.erro = resDescricao.reason?.response?.data?.detail || 'Assistente IA indisponível no momento.'
    }
    if (resUrgencia.status === 'fulfilled') {
      const dados = resUrgencia.value.data?.data
      if (dados?.urgencia) {
        form.urgencia = dados.urgencia
        ia.urgenciaSugerida = dados.urgencia
        ia.justificativa = dados.justificativa || ''
      }
    }
  } catch (err) {
    ia.erro = err?.response?.data?.detail || 'Erro ao contatar o Assistente IA.'
  } finally {
    ia.carregando = false
  }
}
</script>

<style scoped>
.requisitos-subtitle { max-width: 58ch; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.summary-card { padding: 16px; }
.summary-value { font-size: 30px; font-weight: 800; color: var(--accent); }
.summary-filter, .filter-subtitle { font-size: 12px; }
.filter-card { padding: 16px; }
.filter-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.filter-actions { display: flex; justify-content: flex-end; }
@media (max-width: 720px) {
  .header-actions, .filter-actions { justify-content: stretch; }
  .header-actions :deep(.v-btn), .filter-actions :deep(.v-btn) { width: 100%; }
  .requisitos-table :deep(table) { min-width: 760px; }
}
</style>
