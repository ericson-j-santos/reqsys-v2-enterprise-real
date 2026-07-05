<template>
  <section class="financeiro-page" data-testid="route-financeiro" aria-labelledby="titulo-financeiro">
    <div class="financeiro-header">
      <div>
        <p class="eyebrow">ReqSys · Financeiro</p>
        <h1 id="titulo-financeiro">CDI</h1>
        <p class="muted">
          Provedor interno e gratuito da taxa CDI diária, com o Banco Central (série SGS 12) como fonte
          primária e cache local governado. A autorização e auditoria da fonte estão registradas em
          <code>config/external-sources-registry.json</code> (fonte <code>bcb-sgs-cdi</code>).
        </p>
      </div>
      <v-btn
        v-if="podeAtualizar"
        color="primary"
        variant="tonal"
        :loading="atualizando"
        data-testid="financeiro-btn-refresh"
        @click="atualizar"
      >
        <v-icon icon="mdi-refresh" start />
        Atualizar do Banco Central
      </v-btn>
    </div>

    <v-alert
      v-if="modoOffline"
      type="warning"
      variant="tonal"
      class="mt-2"
      role="alert"
      data-testid="financeiro-modo-offline"
    >
      <strong>Modo offline</strong> — {{ mensagem }}
    </v-alert>

    <v-alert
      v-else-if="!cdi && mensagem"
      type="info"
      variant="tonal"
      class="mt-2"
      role="status"
      data-testid="financeiro-sem-cache"
    >
      {{ mensagem }}
    </v-alert>

    <v-alert
      v-if="avisoAtualizacao"
      type="warning"
      variant="tonal"
      class="mt-2"
      role="alert"
      data-testid="financeiro-aviso-atualizacao"
    >
      <strong>Falha ao consultar o Banco Central</strong> — {{ avisoAtualizacao }}
    </v-alert>

    <v-alert
      v-if="erroAtualizacao"
      type="error"
      variant="tonal"
      class="mt-2"
      role="alert"
      data-testid="financeiro-erro-atualizacao"
    >
      {{ erroAtualizacao }}
    </v-alert>

    <v-row v-if="cdi" class="mt-4" dense>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Taxa diária (%)"
          :value="formatarPercentual(cdi.daily_rate_percent)"
          semaforo="verde"
          icon="mdi-percent-outline"
          :clickable="false"
          test-id="financeiro-card-percentual"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Taxa diária (decimal)"
          :value="cdi.daily_rate_decimal"
          semaforo="verde"
          icon="mdi-decimal"
          :clickable="false"
          test-id="financeiro-card-decimal"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Referência"
          :value="cdi.reference_date"
          semaforo="verde"
          icon="mdi-calendar-check-outline"
          :clickable="false"
          test-id="financeiro-card-referencia"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <OperationalMetricCard
          label="Cache"
          :value="cdi.stale ? 'Desatualizado' : 'Atualizado'"
          :semaforo="cdi.stale ? 'amarelo' : 'verde'"
          icon="mdi-database-clock-outline"
          :clickable="false"
          test-id="financeiro-card-cache"
        />
      </v-col>
    </v-row>

    <v-card v-if="cdi" class="panel mt-4" elevation="0">
      <v-card-title>Analítico e fonte</v-card-title>
      <v-card-text>
        <dl class="metadata">
          <div><dt>Fonte</dt><dd>{{ cdi.source }}</dd></div>
          <div><dt>Confiabilidade</dt><dd>alta</dd></div>
          <div><dt>Coletado em</dt><dd>{{ formatarData(cdi.fetched_at) }}</dd></div>
          <div><dt>Tipo</dt><dd>externa · pública</dd></div>
          <div class="full"><dt>URL da fonte</dt><dd><a :href="cdi.source_url" target="_blank" rel="noopener">{{ cdi.source_url }}</a></dd></div>
          <div class="full">
            <dt>Fórmula</dt>
            <dd>Taxa diária extraída diretamente da série SGS 12 do Banco Central (sem cálculo adicional); percentual convertido para decimal dividindo por 100.</dd>
          </div>
        </dl>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import { atualizarCdi, carregarCdiAtual, formatarPercentual } from '../services/financeiro'

const auth = useAuthStore()
const cdi = ref(null)
const modoOffline = ref(false)
const mensagem = ref('')
const atualizando = ref(false)
const avisoAtualizacao = ref('')
const erroAtualizacao = ref('')

const podeAtualizar = computed(() => auth.usuario?.papel === 'admin')

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

async function carregar() {
  const resultado = await carregarCdiAtual()
  modoOffline.value = resultado.modoOffline
  mensagem.value = resultado.mensagem
  cdi.value = resultado.cdi
}

async function atualizar() {
  atualizando.value = true
  avisoAtualizacao.value = ''
  erroAtualizacao.value = ''
  try {
    const resposta = await atualizarCdi()
    cdi.value = resposta.data
    if (resposta.meta?.warning) {
      avisoAtualizacao.value = resposta.meta.detail || resposta.meta.warning
    } else {
      modoOffline.value = false
      mensagem.value = ''
    }
  } catch (erro) {
    erroAtualizacao.value = erro?.response?.data?.detail || 'Falha ao atualizar a taxa CDI no Banco Central.'
  } finally {
    atualizando.value = false
  }
}

onMounted(carregar)
</script>

<style scoped>
.financeiro-page { display: flex; flex-direction: column; gap: 8px; }
.financeiro-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 4px; }
.metadata div { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px; }
.metadata .full { grid-column: 1 / -1; }
dt { font-weight: 700; font-size: 12px; color: var(--text-muted, #6b7280); }
dd { margin: 4px 0 0; word-break: break-word; }
@media (max-width: 700px) { .metadata { grid-template-columns: 1fr; } }
</style>
