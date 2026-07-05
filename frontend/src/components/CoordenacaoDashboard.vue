<!--
  CoordenacaoDashboard — painel genérico de coordenação de demandas.

  Reutilizado por duas telas:
    - Orquestrador IA por tema      (basePath="/v1/agents/orchestrator",     variante="tematico")
    - Coordenação Geral de ADRs     (basePath="/v1/agents/adr-orchestrator", variante="adr")

  Ambas as APIs seguem o mesmo contrato de rotas (coordinators, route, route/batch,
  analytics/summary, analytics/<dimensao>, analytics/coordinators, analytics/risk);
  as diferenças de formato de payload são normalizadas internamente por variante.
-->
<template>
  <section class="coordenacao-page" :data-testid="`coordenacao-${variante}`" aria-labelledby="titulo-coordenacao">
    <div class="coordenacao-header">
      <div>
        <p class="eyebrow">ReqSys · Coordenação assistida</p>
        <h1 id="titulo-coordenacao">{{ titulo }}</h1>
        <p class="muted">{{ subtitulo }}</p>
      </div>
      <v-chip :color="healthInfo ? 'success' : 'grey'" variant="tonal" size="large">
        {{ healthInfo ? `${coordenadoresNormalizados.length} coordenador(es) ativo(s)` : 'Verificando saúde…' }}
      </v-chip>
    </div>

    <v-alert v-if="errorMessage" type="warning" variant="tonal" class="mt-2" closable @click:close="errorMessage = ''">
      {{ errorMessage }}
    </v-alert>

    <v-row class="mt-4" dense>
      <v-col v-for="card in cardsResumo" :key="card.id" cols="12" sm="6" lg="3">
        <OperationalMetricCard
          :label="card.label"
          :value="card.value"
          :semaforo="card.semaforo"
          :icon="card.icon"
          :clickable="false"
          :test-id="`coordenacao-${variante}-card-${card.id}`"
        />
      </v-col>
    </v-row>

    <v-row class="mt-2" dense>
      <v-col cols="12" lg="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Coordenadores sob a coordenação geral</v-card-title>
          <v-card-text>
            <v-row dense>
              <v-col v-for="coord in coordenadoresNormalizados" :key="coord.id" cols="12" md="6">
                <v-card class="coord-card" elevation="0">
                  <div class="coord-card__top">
                    <strong>{{ coord.chave }}</strong>
                    <span v-if="coord.selo" class="coord-card__selo">{{ coord.selo }}</span>
                  </div>
                  <p class="coord-card__nome">{{ coord.nome }}</p>
                  <div class="coord-card__tags">
                    <v-chip v-for="tag in coord.tags.slice(0, 4)" :key="tag" size="x-small" variant="tonal">{{ tag }}</v-chip>
                  </div>
                  <p v-if="coord.automacoes[0]" class="coord-card__automacao">↳ {{ coord.automacoes[0] }}</p>
                </v-card>
              </v-col>
              <v-col v-if="!coordenadoresNormalizados.length" cols="12">
                <p class="muted">Nenhum coordenador carregado.</p>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Classificar nova demanda</v-card-title>
          <v-card-text>
            <v-text-field v-model="form.titulo" label="Título" density="comfortable" variant="outlined" maxlength="180" />
            <v-textarea v-model="form.descricao" label="Descrição" rows="3" density="comfortable" variant="outlined" maxlength="4000" />
            <v-row dense>
              <v-col cols="12" sm="4">
                <v-text-field v-model="form.origem" label="Origem" density="comfortable" variant="outlined" maxlength="80" />
              </v-col>
              <v-col cols="12" sm="4">
                <v-select v-model="form.prioridade_informada" :items="opcoesPrioridade" label="Prioridade" density="comfortable" variant="outlined" clearable />
              </v-col>
              <v-col cols="12" sm="4">
                <v-select v-model="form.ambiente" :items="opcoesAmbiente" label="Ambiente" density="comfortable" variant="outlined" clearable />
              </v-col>
            </v-row>
            <div class="d-flex justify-end">
              <v-btn color="primary" prepend-icon="mdi-compass-outline" :loading="enviando" :disabled="form.titulo.trim().length < 3" @click="enviarDemanda">
                Classificar e rotear
              </v-btn>
            </div>

            <v-alert v-if="resultadoErro" type="error" variant="tonal" class="mt-3">{{ resultadoErro }}</v-alert>

            <v-card v-if="resultado" class="resultado-card mt-4" elevation="0">
              <div class="resultado-card__top">
                <div>
                  <strong>{{ resultado.coordenadorChave }}</strong> — {{ resultado.coordenadorNome }}
                </div>
                <SemaforoChip :value="semaforoResultado" size="small" />
              </div>
              <div class="resultado-card__meta">
                <v-chip size="small">Score {{ resultado.score }}</v-chip>
                <v-chip size="small">Confiança {{ Math.round(resultado.confianca * 100) }}%</v-chip>
                <v-chip size="small">Prioridade {{ resultado.prioridade }}</v-chip>
                <v-chip v-if="resultado.status" size="small">{{ resultado.status === 'proposed' ? 'Proposto' : 'Aceito' }}</v-chip>
                <v-chip v-if="resultado.nivelAutonomia" size="small">Autonomia {{ resultado.nivelAutonomia }}</v-chip>
              </div>
              <v-alert v-if="resultado.violacoes.length" type="error" variant="tonal" class="mt-2" density="compact">
                <strong>Violação(ões) de gate detectada(s):</strong> {{ resultado.violacoes.join(', ') }}
              </v-alert>
              <div v-if="resultado.relacionados.length" class="mt-2">
                <span class="muted">ADRs relacionados:</span>
                <v-chip v-for="rel in resultado.relacionados" :key="rel" size="x-small" variant="tonal" class="ml-1">{{ rel }}</v-chip>
              </div>
              <p class="mt-2"><strong>Próximo passo:</strong> {{ resultado.proximoPasso }}</p>
              <div class="d-flex ga-1 flex-wrap mt-1">
                <v-chip v-for="label in resultado.labels" :key="label" size="x-small" variant="outlined">{{ label }}</v-chip>
              </div>
            </v-card>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-2" dense>
      <v-col cols="12" md="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Distribuição por {{ dimensaoLabel }}</v-card-title>
          <v-card-text>
            <v-table density="compact">
              <thead><tr><th>{{ dimensaoLabel }}</th><th>Eventos</th></tr></thead>
              <tbody>
                <tr v-for="item in dimensaoBreakdown" :key="item.valor">
                  <td>{{ item.valor }}</td>
                  <td>{{ item.total }}</td>
                </tr>
                <tr v-if="!dimensaoBreakdown.length"><td colspan="2" class="muted">Sem eventos registrados ainda.</td></tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card class="panel" elevation="0">
          <v-card-title>Indicadores de risco</v-card-title>
          <v-card-text>
            <div class="d-flex ga-2 flex-wrap">
              <v-chip v-for="(valor, chave) in risco" :key="chave" :color="valor > 0 ? 'warning' : 'success'" variant="tonal">
                {{ rotuloRisco(chave) }}: {{ valor }}
              </v-chip>
              <span v-if="!Object.keys(risco).length" class="muted">Sem indicadores ainda.</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import OperationalMetricCard from './OperationalMetricCard.vue'
import SemaforoChip from './SemaforoChip.vue'
import {
  carregarAnalyticsDimensao,
  carregarAnalyticsResumo,
  carregarAnalyticsRisco,
  classificarDemanda,
  listarCoordenadores,
  verificarHealthCoordenacao,
} from '../services/coordenadores'

const props = defineProps({
  basePath: { type: String, required: true },
  variante: { type: String, required: true, validator: (v) => ['tematico', 'adr'].includes(v) },
  titulo: { type: String, required: true },
  subtitulo: { type: String, default: '' },
})

const VARIANTES = {
  tematico: {
    dimensaoLabel: 'Tema',
    dimensaoEndpoint: 'themes',
    normalizarCoordenador: (c) => ({
      id: c.coordinator_id,
      chave: c.tema,
      nome: c.nome,
      selo: c.destino_operacional,
      tags: c.labels || [],
      automacoes: c.automacoes || [],
    }),
    normalizarResultado: (data) => ({
      coordenadorNome: data.coordinator.nome,
      coordenadorChave: data.tema,
      status: null,
      score: data.score,
      confianca: data.confianca,
      prioridade: data.prioridade_sugerida,
      requerAprovacao: Boolean(data.governanca?.requer_aprovacao_humana),
      nivelAutonomia: null,
      labels: data.labels || [],
      proximoPasso: data.proximo_passo,
      violacoes: [],
      relacionados: [],
    }),
  },
  adr: {
    dimensaoLabel: 'ADR',
    dimensaoEndpoint: 'adrs',
    normalizarCoordenador: (c) => ({
      id: c.coordinator_id,
      chave: c.adr_id,
      nome: c.nome,
      selo: c.status === 'proposed' ? 'Proposto' : 'Aceito',
      tags: c.palavras_chave || [],
      automacoes: c.automacoes || [],
    }),
    normalizarResultado: (data) => ({
      coordenadorNome: data.adr_primario.nome,
      coordenadorChave: data.adr_primario.adr_id,
      status: data.adr_primario.status,
      score: data.adr_primario.score,
      confianca: data.confianca,
      prioridade: data.prioridade_sugerida,
      requerAprovacao: Boolean(data.governanca?.requer_aprovacao_humana),
      nivelAutonomia: data.governanca?.nivel_autonomia_sugerido || null,
      labels: data.labels || [],
      proximoPasso: data.proximo_passo,
      violacoes: (data.violacoes_detectadas || []).map((v) => v.violacao),
      relacionados: (data.adrs_relacionados || []).map((r) => `${r.adr_id} · ${r.nome}`),
    }),
  },
}

const RISCO_LABELS = {
  prioridade_alta: 'Prioridade alta',
  baixa_confianca: 'Baixa confiança',
  alto_score: 'Score alto',
  nivel_critico: 'Nível crítico',
  nivel_alto: 'Nível alto',
  com_violacao_de_gate: 'Com violação de gate',
}

function rotuloRisco(chave) {
  return RISCO_LABELS[chave] || chave.replace(/_/g, ' ')
}

const config = computed(() => VARIANTES[props.variante])
const dimensaoLabel = computed(() => config.value.dimensaoLabel)

const errorMessage = ref('')
const healthInfo = ref(null)
const coordenadores = ref([])
const resumo = ref({ total_eventos: 0, score_medio: 0, confianca_media: 0 })
const dimensaoBreakdown = ref([])
const risco = ref({})

const opcoesPrioridade = [
  { title: 'Normal', value: 'normal' },
  { title: 'Média', value: 'media' },
  { title: 'Alta', value: 'alta' },
]
const opcoesAmbiente = [
  { title: 'Desenvolvimento', value: 'dev' },
  { title: 'Homologação', value: 'hml' },
  { title: 'Produção', value: 'prod' },
]

const form = reactive({ titulo: '', descricao: '', origem: 'chat', prioridade_informada: null, ambiente: null })
const enviando = ref(false)
const resultado = ref(null)
const resultadoErro = ref('')

const coordenadoresNormalizados = computed(() => coordenadores.value.map(config.value.normalizarCoordenador))

const semaforoResultado = computed(() => {
  if (!resultado.value) return 'desconhecido'
  if (resultado.value.violacoes.length) return 'vermelho'
  if (resultado.value.requerAprovacao) return 'amarelo'
  return 'verde'
})

const cardsResumo = computed(() => [
  { id: 'eventos', label: 'Eventos classificados', value: resumo.value.total_eventos ?? 0, semaforo: 'verde', icon: 'mdi-counter' },
  { id: 'score', label: 'Score médio', value: resumo.value.score_medio ?? 0, semaforo: 'verde', icon: 'mdi-chart-arc' },
  { id: 'confianca', label: 'Confiança média', value: `${Math.round((resumo.value.confianca_media ?? 0) * 100)}%`, semaforo: (resumo.value.confianca_media ?? 0) >= 0.7 ? 'verde' : 'amarelo', icon: 'mdi-shield-check-outline' },
  { id: 'risco', label: 'Sinais de risco', value: Object.values(risco.value).reduce((soma, valor) => soma + valor, 0), semaforo: Object.values(risco.value).some((v) => v > 0) ? 'vermelho' : 'verde', icon: 'mdi-alert-outline' },
])

function acumularErro(resposta, mensagemPadrao) {
  if (!resposta.ok) {
    errorMessage.value = resposta.erro || mensagemPadrao
    return null
  }
  return resposta.dados
}

async function carregarAnalytics() {
  const [respostaResumo, respostaDimensao, respostaRisco] = await Promise.all([
    carregarAnalyticsResumo(props.basePath),
    carregarAnalyticsDimensao(props.basePath, config.value.dimensaoEndpoint),
    carregarAnalyticsRisco(props.basePath),
  ])
  const dadosResumo = acumularErro(respostaResumo, 'Falha ao carregar resumo analítico.')
  if (dadosResumo) resumo.value = dadosResumo

  const dadosDimensao = acumularErro(respostaDimensao, 'Falha ao carregar analítico por dimensão.')
  if (dadosDimensao) dimensaoBreakdown.value = dadosDimensao[config.value.dimensaoEndpoint] || []

  const dadosRisco = acumularErro(respostaRisco, 'Falha ao carregar indicadores de risco.')
  if (dadosRisco) risco.value = dadosRisco.risk || {}
}

async function carregarTudo() {
  const [respostaHealth, respostaCoordenadores] = await Promise.all([
    verificarHealthCoordenacao(props.basePath),
    listarCoordenadores(props.basePath),
  ])
  healthInfo.value = acumularErro(respostaHealth, 'Falha ao verificar saúde da coordenação.')
  const dadosCoordenadores = acumularErro(respostaCoordenadores, 'Falha ao carregar coordenadores.')
  if (dadosCoordenadores) coordenadores.value = dadosCoordenadores.coordinators || []
  await carregarAnalytics()
}

async function enviarDemanda() {
  resultadoErro.value = ''
  enviando.value = true
  try {
    const resposta = await classificarDemanda(props.basePath, { ...form })
    if (!resposta.ok) {
      resultadoErro.value = resposta.erro || 'Falha ao classificar demanda.'
      return
    }
    resultado.value = config.value.normalizarResultado(resposta.dados)
    await carregarAnalytics()
  } finally {
    enviando.value = false
  }
}

onMounted(carregarTudo)
</script>

<style scoped>
.coordenacao-page { display: flex; flex-direction: column; gap: 8px; }
.coordenacao-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.coord-card { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; padding: 12px; height: 100%; }
.coord-card__top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.coord-card__selo { font-size: 11px; color: var(--text-muted, #6b7280); }
.coord-card__nome { margin: 4px 0 8px; font-size: 13px; }
.coord-card__tags { display: flex; flex-wrap: wrap; gap: 4px; }
.coord-card__automacao { margin: 8px 0 0; font-size: 12px; color: var(--text-muted, #6b7280); }
.resultado-card { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 12px; padding: 12px; }
.resultado-card__top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.resultado-card__meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
</style>
