<template>
  <div>
    <div class="d-flex flex-wrap align-center justify-space-between gap-3 mb-6">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Requisitos</div>
        <div class="text-body-2 text-medium-emphasis">Gestão e rastreamento de requisitos do sistema</div>
      </div>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="abrirDialog()">
        Novo Requisito
      </v-btn>
    </div>

    <!-- Filtros -->
    <v-card rounded="xl" :elevation="1" class="mb-4">
      <v-card-text class="pa-4">
        <v-row dense align="center">
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              v-model="busca"
              placeholder="Buscar por título ou solicitante..."
              prepend-inner-icon="mdi-magnify"
              variant="outlined"
              density="compact"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="6" sm="3" md="2">
            <v-select
              v-model="filtroStatus"
              :items="statusOpcoes"
              label="Status"
              variant="outlined"
              density="compact"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="6" sm="3" md="2">
            <v-select
              v-model="filtroUrgencia"
              :items="urgenciaOpcoes"
              label="Urgência"
              variant="outlined"
              density="compact"
              hide-details
              clearable
            />
          </v-col>
          <v-col cols="12" md="4" class="d-flex justify-end gap-2">
            <v-chip color="primary" variant="tonal" size="small">
              {{ requisitorsFiltrados.length }} resultado(s)
            </v-chip>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Tabela -->
    <v-card rounded="xl" :elevation="2">
      <v-data-table
        :headers="headers"
        :items="requisitorsFiltrados"
        :loading="carregando"
        density="comfortable"
        hover
        item-value="id"
      >
        <template #item.titulo="{ item }">
          <div class="font-weight-medium">{{ item.titulo }}</div>
          <div class="text-caption text-medium-emphasis">{{ item.sistema }}</div>
        </template>
        <template #item.status="{ item }">
          <v-chip :color="corStatus(item.status)" size="x-small" variant="tonal">
            {{ item.status }}
          </v-chip>
        </template>
        <template #item.urgencia="{ item }">
          <v-chip :color="corUrgencia(item.urgencia)" size="x-small" variant="tonal">
            {{ item.urgencia }}
          </v-chip>
        </template>
        <template #item.actions="{ item }">
          <v-btn icon="mdi-eye-outline" variant="text" size="small" color="primary" :to="`/requisitos/${item.id}`" />
          <v-btn icon="mdi-pencil-outline" variant="text" size="small" @click="abrirDialog(item)" />
        </template>
        <template #no-data>
          <v-alert type="info" variant="tonal" class="ma-4">
            Nenhum requisito encontrado.
          </v-alert>
        </template>
      </v-data-table>
    </v-card>

    <!-- Dialog Novo/Editar -->
    <v-dialog v-model="dialogAberto" max-width="760" scrollable>
      <v-card rounded="xl">
        <v-card-title class="pa-6 pb-2">
          {{ editando ? 'Editar Requisito' : 'Novo Requisito' }}
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-6">
          <v-row dense>
            <v-col cols="12">
              <v-text-field v-model="form.titulo" label="Título *" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-select v-model="form.urgencia" :items="urgenciaOpcoes" label="Urgência *" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-select v-model="form.status" :items="statusOpcoes" label="Status" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.area" label="Área" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.sistema" label="Sistema" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12">
              <v-text-field v-model="form.solicitante" label="Solicitante" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12">
              <v-textarea v-model="form.descricao" label="Descrição" variant="outlined" rows="4" auto-grow />
            </v-col>
          </v-row>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="dialogAberto = false">Cancelar</v-btn>
          <v-btn color="primary" :loading="salvando" @click="salvar">
            {{ editando ? 'Salvar' : 'Criar' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'

const carregando = ref(true)
const salvando = ref(false)
const dialogAberto = ref(false)
const editando = ref(false)
const busca = ref('')
const filtroStatus = ref(null)
const filtroUrgencia = ref(null)
const requisitos = ref([])

const form = ref({ titulo: '', urgencia: 'MÉDIA', status: 'ABERTO', area: '', sistema: '', solicitante: '', descricao: '' })

const statusOpcoes = ['ABERTO', 'EM_ANÁLISE', 'APROVADO', 'REJEITADO', 'IMPLEMENTADO']
const urgenciaOpcoes = ['BAIXA', 'MÉDIA', 'ALTA', 'CRÍTICA']

const headers = [
  { title: 'Título / Sistema', key: 'titulo', sortable: true },
  { title: 'Área', key: 'area', sortable: true },
  { title: 'Solicitante', key: 'solicitante', sortable: true },
  { title: 'Urgência', key: 'urgencia', sortable: true, width: 120 },
  { title: 'Status', key: 'status', sortable: true, width: 150 },
  { title: '', key: 'actions', sortable: false, width: 110 },
]

const requisitorsFiltrados = computed(() => {
  return requisitos.value.filter(r => {
    const buscaOk = !busca.value || r.titulo?.toLowerCase().includes(busca.value.toLowerCase()) || r.solicitante?.toLowerCase().includes(busca.value.toLowerCase())
    const statusOk = !filtroStatus.value || r.status === filtroStatus.value
    const urgenciaOk = !filtroUrgencia.value || r.urgencia === filtroUrgencia.value
    return buscaOk && statusOk && urgenciaOk
  })
})

function corStatus(s) {
  return { ABERTO: 'info', EM_ANÁLISE: 'warning', APROVADO: 'success', REJEITADO: 'error', IMPLEMENTADO: 'secondary' }[s] || 'default'
}
function corUrgencia(u) {
  return { BAIXA: 'success', MÉDIA: 'info', ALTA: 'warning', CRÍTICA: 'error' }[u] || 'default'
}

function abrirDialog(item = null) {
  editando.value = !!item
  form.value = item
    ? { ...item }
    : { titulo: '', urgencia: 'MÉDIA', status: 'ABERTO', area: '', sistema: '', solicitante: '', descricao: '' }
  dialogAberto.value = true
}

async function salvar() {
  salvando.value = true
  try {
    if (editando.value) {
      const { data } = await api.put(`/v1/requisitos/${form.value.id}`, form.value)
      const idx = requisitos.value.findIndex(r => r.id === form.value.id)
      if (idx !== -1) requisitos.value[idx] = data
    } else {
      const { data } = await api.post('/v1/requisitos', form.value)
      requisitos.value.unshift(data)
    }
    dialogAberto.value = false
  } catch (e) {
    console.error(e)
  } finally {
    salvando.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await api.get('/v1/requisitos')
    requisitos.value = data.items ?? data
  } catch {
    requisitos.value = [
      { id: 1, titulo: 'Autenticação SSO', sistema: 'Portal', area: 'TI', solicitante: 'João Silva', urgencia: 'ALTA', status: 'APROVADO' },
      { id: 2, titulo: 'Exportar relatório PDF', sistema: 'SSRS', area: 'Financeiro', solicitante: 'Maria Costa', urgencia: 'MÉDIA', status: 'ABERTO' },
      { id: 3, titulo: 'Dashboard executivo', sistema: 'BI', area: 'Diretoria', solicitante: 'Pedro Alves', urgencia: 'CRÍTICA', status: 'EM_ANÁLISE' },
    ]
  } finally {
    carregando.value = false
  }
})
</script>
