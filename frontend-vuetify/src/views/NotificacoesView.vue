<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useNotificacoesStore } from '../stores/notificacoes'

const store = useNotificacoesStore()

const aviso = ref({ visivel: false, mensagem: '', cor: 'success' })
const filtroAtivo = ref(null)
const reprocessandoId = ref(null)

const filtros = [
  { rotulo: 'Todos',       valor: null },
  { rotulo: 'Pendente',    valor: 'PENDENTE' },
  { rotulo: 'Processando', valor: 'PROCESSANDO' },
  { rotulo: 'Enviado',     valor: 'ENVIADO' },
  { rotulo: 'Falha',       valor: 'FALHA' },
  { rotulo: 'Cancelado',   valor: 'CANCELADO' },
]

const coresPorStatus = {
  PENDENTE:    'warning',
  PROCESSANDO: 'info',
  ENVIADO:     'success',
  FALHA:       'error',
  CANCELADO:   'default',
}

function corPorStatus(status) {
  return coresPorStatus[status] ?? 'default'
}

function formatarData(valor) {
  if (!valor) return '—'
  const d = new Date(valor)
  if (isNaN(d.getTime())) return valor
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

const kpis = computed(() => [
  { titulo: 'Pendentes',   valor: store.dashboard?.pendentes   ?? 0, cor: 'warning', icon: 'mdi-clock-outline'   },
  { titulo: 'Processando', valor: store.dashboard?.processando ?? 0, cor: 'info',    icon: 'mdi-sync'            },
  { titulo: 'Enviados',    valor: store.dashboard?.enviados    ?? 0, cor: 'success', icon: 'mdi-check-circle'    },
  { titulo: 'Falhas',      valor: store.dashboard?.falhas      ?? 0, cor: 'error',   icon: 'mdi-alert-circle'    },
])

const carregando = computed(() =>
  store.carregandoDashboard || store.carregandoFila ||
  store.carregandoDlq       || store.carregandoLogs,
)

async function aplicarFiltro(valor) {
  filtroAtivo.value = valor
  await store.carregarFila(valor)
}

async function reprocessar(idDlq) {
  reprocessandoId.value = idDlq
  try {
    await store.reprocessarDlq(idDlq)
    aviso.value = { visivel: true, mensagem: 'Item reprocessado com sucesso.', cor: 'success' }
  } catch {
    aviso.value = { visivel: true, mensagem: 'Erro ao reprocessar. Tente novamente.', cor: 'error' }
  } finally {
    reprocessandoId.value = null
  }
}

const INTERVALO_MS = 30_000
let timer = null

onMounted(() => {
  store.carregarTudo()
  timer = setInterval(() => { if (!carregando.value) store.carregarTudo() }, INTERVALO_MS)
})

onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="notificacoes-page">

    <!-- Cabeçalho -->
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Notificações Teams</div>
        <div class="text-body-2 text-medium-emphasis">
          Monitoramento da fila de envio, falhas (DLQ) e registros de auditoria.
        </div>
      </div>
      <v-btn
        variant="outlined"
        prepend-icon="mdi-refresh"
        :loading="carregando"
        @click="store.carregarTudo()"
      >
        Atualizar
      </v-btn>
    </div>

    <!-- Alerta de erro global -->
    <v-alert
      v-if="store.erro"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="store.erro = null"
    >
      {{ store.erro }}
    </v-alert>

    <!-- KPIs -->
    <v-row dense class="mb-4">
      <v-col v-for="kpi in kpis" :key="kpi.titulo" cols="6" md="3">
        <v-skeleton-loader v-if="store.carregandoDashboard" type="card" height="88" />
        <v-card v-else :color="kpi.cor" variant="tonal" rounded="lg">
          <v-card-text class="d-flex align-center ga-3 pa-4">
            <v-icon :icon="kpi.icon" :color="kpi.cor" size="32" />
            <div>
              <div class="text-h5 font-weight-bold">{{ kpi.valor }}</div>
              <div class="text-caption text-medium-emphasis">{{ kpi.titulo }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Fila + DLQ -->
    <v-row class="mb-4">

      <!-- Fila de envio -->
      <v-col cols="12" lg="8">
        <v-card rounded="xl" elevation="1" class="panel-card">
          <div class="d-flex flex-wrap align-center justify-space-between pa-4 pb-2 ga-2">
            <span class="text-subtitle-1 font-weight-medium">Fila de Envio</span>
            <div class="d-flex flex-wrap ga-1">
              <v-chip
                v-for="f in filtros"
                :key="String(f.valor)"
                size="small"
                :variant="filtroAtivo === f.valor ? 'flat' : 'tonal'"
                :color="filtroAtivo === f.valor ? 'primary' : undefined"
                @click="aplicarFiltro(f.valor)"
              >
                {{ f.rotulo }}
              </v-chip>
            </div>
          </div>
          <v-divider />

          <v-skeleton-loader v-if="store.carregandoFila" type="table-row@5" class="pa-2" />

          <div v-else-if="!store.fila.length" class="text-center pa-10 text-medium-emphasis">
            <v-icon icon="mdi-inbox-outline" size="48" class="mb-3" style="opacity:.3" />
            <div class="text-body-2">Nenhum item na fila</div>
          </div>

          <div v-else class="overflow-x-auto">
            <v-table density="comfortable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Destino</th>
                  <th>Título</th>
                  <th>Status</th>
                  <th class="text-center">Tent.</th>
                  <th>Criado em</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in store.fila" :key="item.id_evento">
                  <td>{{ item.id_evento }}</td>
                  <td class="text-truncate" style="max-width:180px" :title="item.upn_destino ?? ''">
                    {{ item.upn_destino ?? '—' }}
                  </td>
                  <td class="text-truncate" style="max-width:200px" :title="item.titulo">
                    {{ item.titulo }}
                  </td>
                  <td>
                    <v-chip :color="corPorStatus(item.status_evento)" size="x-small" label>
                      {{ item.status_evento }}
                    </v-chip>
                  </td>
                  <td class="text-center">{{ item.tentativas }}</td>
                  <td style="white-space:nowrap">{{ formatarData(item.criado_em) }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card>
      </v-col>

      <!-- DLQ -->
      <v-col cols="12" lg="4">
        <v-card rounded="xl" elevation="1" class="panel-card">
          <div class="pa-4 pb-2 d-flex align-center justify-space-between">
            <span class="text-subtitle-1 font-weight-medium">Fila de Falhas (DLQ)</span>
            <v-chip v-if="store.dlq.length" color="error" size="x-small" label>
              {{ store.dlq.length }}
            </v-chip>
          </div>
          <v-divider />

          <v-skeleton-loader v-if="store.carregandoDlq" type="table-row@3" class="pa-2" />

          <div v-else-if="!store.dlq.length" class="text-center pa-10 text-medium-emphasis">
            <v-icon icon="mdi-inbox-remove" size="48" class="mb-3" style="opacity:.3" />
            <div class="text-body-2">Nenhuma mensagem na DLQ</div>
          </div>

          <div v-else class="overflow-x-auto">
            <v-table density="comfortable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Destino</th>
                  <th>Motivo</th>
                  <th>Ação</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in store.dlq" :key="item.id_dlq">
                  <td>{{ item.id_dlq }}</td>
                  <td class="text-truncate" style="max-width:120px" :title="item.upn_destino ?? ''">
                    {{ item.upn_destino ?? '—' }}
                  </td>
                  <td class="text-truncate" style="max-width:140px" :title="item.motivo_falha">
                    {{ item.motivo_falha }}
                  </td>
                  <td>
                    <v-btn
                      size="x-small"
                      color="primary"
                      variant="tonal"
                      :loading="reprocessandoId === item.id_dlq"
                      @click="reprocessar(item.id_dlq)"
                    >
                      Reprocessar
                    </v-btn>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Registros de Envio -->
    <v-row>
      <v-col cols="12">
        <v-card rounded="xl" elevation="1" class="panel-card">
          <div class="pa-4 pb-2">
            <span class="text-subtitle-1 font-weight-medium">Registros de Envio</span>
          </div>
          <v-divider />

          <v-skeleton-loader v-if="store.carregandoLogs" type="table-row@5" class="pa-2" />

          <div v-else-if="!store.logs.length" class="text-center pa-10 text-medium-emphasis">
            <v-icon icon="mdi-format-list-bulleted-square" size="48" class="mb-3" style="opacity:.3" />
            <div class="text-body-2">Nenhum registro de envio</div>
          </div>

          <div v-else class="overflow-x-auto">
            <v-table density="comfortable">
              <thead>
                <tr>
                  <th>ID Log</th>
                  <th>ID Evento</th>
                  <th>Etapa</th>
                  <th>Resultado</th>
                  <th>HTTP</th>
                  <th>Detalhe</th>
                  <th>Registrado em</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in store.logs" :key="item.id_log">
                  <td>{{ item.id_log }}</td>
                  <td>{{ item.id_evento }}</td>
                  <td>{{ item.etapa }}</td>
                  <td>
                    <v-chip :color="corPorStatus(item.status_resultado)" size="x-small" label>
                      {{ item.status_resultado }}
                    </v-chip>
                  </td>
                  <td>{{ item.status_http ?? '—' }}</td>
                  <td class="text-truncate" style="max-width:260px" :title="item.detalhe ?? ''">
                    {{ item.detalhe ?? '—' }}
                  </td>
                  <td style="white-space:nowrap">{{ formatarData(item.registrado_em) }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Snackbar de feedback -->
    <v-snackbar
      v-model="aviso.visivel"
      :color="aviso.cor"
      :timeout="4000"
      location="bottom right"
    >
      {{ aviso.mensagem }}
      <template #actions>
        <v-btn variant="text" @click="aviso.visivel = false">Fechar</v-btn>
      </template>
    </v-snackbar>

  </div>
</template>

<style scoped>
.notificacoes-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.overflow-x-auto {
  overflow-x: auto;
}
</style>
