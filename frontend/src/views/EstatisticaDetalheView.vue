<template>
  <section class="detalhe-page" data-testid="route-estatistica-detalhe" aria-labelledby="titulo-indicador">
    <div class="detalhe-actions">
      <v-btn prepend-icon="mdi-arrow-left" variant="text" data-testid="estatistica-detalhe-voltar" @click="voltar">
        Voltar para Estatísticas
      </v-btn>
      <v-btn prepend-icon="mdi-refresh" color="primary" variant="tonal" :loading="carregando" @click="carregar">
        Atualizar
      </v-btn>
    </div>

    <v-alert v-if="erro" type="error" variant="tonal" role="alert" data-testid="estatistica-detalhe-erro">
      {{ erro }}
    </v-alert>

    <v-skeleton-loader v-if="carregando && !detalhe" type="heading, paragraph, card, card, table" />

    <template v-else-if="detalhe?.indicador">
      <header class="detalhe-header">
        <div>
          <p class="eyebrow">REQSYS#004 · Detalhamento operacional</p>
          <h1 id="titulo-indicador">{{ detalhe.indicador.nome }}</h1>
          <p class="muted">{{ detalhe.indicador.descricao }}</p>
        </div>
        <SemaforoChip :value="estadoParaSemaforo(detalhe.indicador.estadoAtual)" size="large" />
      </header>

      <v-alert v-if="detalhe.mensagem" type="warning" variant="tonal" class="mt-2">
        {{ detalhe.mensagem }}
      </v-alert>

      <v-row dense class="mt-3">
        <v-col cols="12" sm="6" lg="3">
          <v-card class="metric-card" elevation="0">
            <span>Valor atual</span>
            <strong>{{ valorAtual }}</strong>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card class="metric-card" elevation="0">
            <span>Estado atual</span>
            <strong>{{ detalhe.indicador.estadoAtual }}</strong>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card class="metric-card" elevation="0">
            <span>Estado alvo</span>
            <strong>{{ detalhe.indicador.estadoAlvo }}</strong>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card class="metric-card" elevation="0">
            <span>Tendência</span>
            <strong>{{ detalhe.tendenciaCalculada }}</strong>
          </v-card>
        </v-col>
      </v-row>

      <v-card class="panel mt-3" elevation="0">
        <v-card-title>Rastreabilidade da coleta</v-card-title>
        <v-card-text>
          <dl class="metadata">
            <div><dt>Indicador</dt><dd>{{ detalhe.indicador.id }}</dd></div>
            <div><dt>Categoria</dt><dd>{{ detalhe.indicador.categoria }}</dd></div>
            <div><dt>Ambiente</dt><dd>{{ detalhe.ambiente || 'não informado' }}</dd></div>
            <div><dt>Coleta</dt><dd>{{ formatarData(detalhe.coletadoEm) }}</dd></div>
            <div class="full"><dt>Correlation ID</dt><dd data-testid="estatistica-detalhe-correlation-id">{{ detalhe.correlationId || 'não informado' }}</dd></div>
          </dl>
        </v-card-text>
      </v-card>

      <v-row dense class="mt-3">
        <v-col cols="12" lg="6">
          <v-card class="panel fill-height" elevation="0">
            <v-card-title>Fonte e fórmula</v-card-title>
            <v-card-text>
              <dl class="metadata">
                <div><dt>Fonte</dt><dd>{{ detalhe.indicador.fonte.nome }}</dd></div>
                <div><dt>Tipo</dt><dd>{{ detalhe.indicador.fonte.tipo }}</dd></div>
                <div><dt>Origem</dt><dd>{{ detalhe.indicador.fonte.origem }}</dd></div>
                <div><dt>Confiabilidade</dt><dd>{{ detalhe.indicador.fonte.confiabilidade }}</dd></div>
                <div><dt>Versão do conector</dt><dd>{{ detalhe.indicador.fonte.versaoConector || 'não informada' }}</dd></div>
                <div><dt>Coleta da fonte</dt><dd>{{ formatarData(detalhe.indicador.fonte.coletadoEm) }}</dd></div>
                <div class="full"><dt>Fórmula</dt><dd>{{ detalhe.indicador.formula }}</dd></div>
              </dl>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" lg="6">
          <v-card class="panel fill-height" elevation="0">
            <v-card-title>Score governado</v-card-title>
            <v-card-text>
              <div v-if="detalhe.scoreEvidenciado !== null" class="score-evidenciado" data-testid="estatistica-score-evidenciado">
                <strong>{{ detalhe.scoreEvidenciado }}%</strong>
                <span>Atualizado exclusivamente por artefato runtime válido.</span>
              </div>
              <v-alert v-else type="warning" variant="tonal" data-testid="estatistica-score-pendente">
                <strong>Score não atualizado.</strong>
                O estado permanece evidenciado sem promoção até existir artefato runtime válido com score verificável.
              </v-alert>

              <dl v-if="detalhe.runtimeArtifactValido" class="metadata mt-3">
                <div><dt>Artefato</dt><dd>runtime verificado</dd></div>
                <div><dt>Status</dt><dd>{{ detalhe.scoreStatus }}</dd></div>
                <div><dt>Run ID</dt><dd>{{ detalhe.runtimeArtifact.source_run_id || detalhe.runtimeArtifact.run_id }}</dd></div>
                <div><dt>Ambiente</dt><dd>{{ detalhe.runtimeArtifact.environment || detalhe.runtimeArtifact.ambiente }}</dd></div>
              </dl>
              <ul v-else class="mt-3">
                <li v-for="motivo in detalhe.runtimeArtifactMotivos" :key="motivo">{{ motivo }}</li>
              </ul>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row dense class="mt-3">
        <v-col cols="12" md="4">
          <v-card class="panel fill-height" elevation="0">
            <v-card-title>Evidências</v-card-title>
            <v-card-text>
              <p v-if="!detalhe.indicador.evidencias?.length" class="muted">Nenhuma evidência registrada.</p>
              <ul>
                <li v-for="item in detalhe.indicador.evidencias" :key="item">{{ item }}</li>
              </ul>
              <v-btn
                v-for="link in detalhe.linksEvidencias"
                :key="link.url"
                :href="link.url"
                target="_blank"
                rel="noopener noreferrer"
                size="small"
                variant="tonal"
                class="mr-2 mt-2"
              >
                Abrir evidência versionada
              </v-btn>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="4">
          <v-card class="panel fill-height" elevation="0">
            <v-card-title>Pendências</v-card-title>
            <v-card-text>
              <p v-if="!detalhe.indicador.pendencias?.length" class="muted">Sem pendências registradas.</p>
              <ul><li v-for="item in detalhe.indicador.pendencias" :key="item">{{ item }}</li></ul>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="4">
          <v-card class="panel fill-height" elevation="0">
            <v-card-title>Guard rails</v-card-title>
            <v-card-text>
              <v-alert v-if="!detalhe.guardRails.length" type="success" variant="tonal">Contrato válido.</v-alert>
              <ul><li v-for="item in detalhe.guardRails" :key="item">{{ item }}</li></ul>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-card class="panel mt-3" elevation="0">
        <v-card-title>Logs, traces e artifacts</v-card-title>
        <v-card-text class="operational-links">
          <template v-for="link in detalhe.linksOperacionais" :key="link.tipo">
            <v-btn
              v-if="link.externo"
              :href="link.url"
              target="_blank"
              rel="noopener noreferrer"
              variant="tonal"
              color="primary"
            >
              {{ link.titulo }}
            </v-btn>
            <v-btn v-else :to="link.url" variant="tonal" color="primary">
              {{ link.titulo }}
            </v-btn>
          </template>
        </v-card-text>
      </v-card>

      <v-card class="panel mt-3" elevation="0">
        <v-card-title>Histórico e tendência</v-card-title>
        <v-card-subtitle>{{ detalhe.historico.length }} ponto(s) histórico(s) para este indicador</v-card-subtitle>
        <v-card-text>
          <v-alert v-if="!detalhe.historico.length" type="info" variant="tonal">
            Histórico ainda não disponível. O estado atual não foi promovido.
          </v-alert>
          <div v-else class="history-table">
            <v-table density="compact">
              <thead>
                <tr><th>Coleta</th><th>Valor</th><th>Estado</th><th>Tendência</th><th>Ambiente</th><th>Correlation ID</th></tr>
              </thead>
              <tbody>
                <tr v-for="ponto in detalhe.historico" :key="`${ponto.coletadoEm}-${ponto.correlationId}`">
                  <td>{{ formatarData(ponto.coletadoEm) }}</td>
                  <td>{{ ponto.valor }}{{ ponto.unidade }}</td>
                  <td>{{ ponto.estado }}</td>
                  <td>{{ ponto.tendencia }}</td>
                  <td>{{ ponto.ambiente || '-' }}</td>
                  <td>{{ ponto.correlationId || '-' }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card-text>
      </v-card>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SemaforoChip from '../components/SemaforoChip.vue'
import { estadoParaSemaforo } from '../utils/filtrosMonitoramento'
import { carregarDetalheIndicador, resolverRetornoEstatisticas } from '../services/estatisticas'

const route = useRoute()
const router = useRouter()
const detalhe = ref(null)
const carregando = ref(false)
const erro = ref('')

const valorAtual = computed(() => {
  const indicador = detalhe.value?.indicador
  return indicador ? `${indicador.valorAtual}${indicador.unidade || ''}` : '-'
})

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const resultado = await carregarDetalheIndicador(String(route.params.indicadorId || ''), route.query.correlation_id || null)
    detalhe.value = resultado
    if (resultado.modoOffline || resultado.naoEncontrado) erro.value = resultado.mensagem
  } catch (e) {
    erro.value = e?.message || 'Falha inesperada ao carregar o indicador.'
  } finally {
    carregando.value = false
  }
}

function voltar() {
  router.push(resolverRetornoEstatisticas(route.query.returnTo))
}

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

watch(() => route.params.indicadorId, carregar)
onMounted(carregar)
</script>

<style scoped>
.detalhe-page { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.detalhe-actions, .detalhe-header, .operational-links { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.detalhe-header { align-items: flex-start; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel, .metric-card { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.metric-card { padding: 16px; height: 100%; }
.metric-card span, .score-evidenciado span { display: block; color: var(--text-muted, #6b7280); font-size: 12px; }
.metric-card strong { display: block; margin-top: 8px; font-size: clamp(20px, 3vw, 28px); word-break: break-word; }
.metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.metadata div { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px; min-width: 0; }
.metadata .full { grid-column: 1 / -1; }
dt { font-weight: 700; font-size: 12px; color: var(--text-muted, #6b7280); }
dd { margin: 4px 0 0; overflow-wrap: anywhere; }
ul { padding-left: 18px; }
.score-evidenciado strong { display: block; font-size: 40px; }
.operational-links { justify-content: flex-start; }
.history-table { width: 100%; overflow-x: auto; }
@media (max-width: 700px) {
  .metadata { grid-template-columns: 1fr; }
  .metadata .full { grid-column: auto; }
  .detalhe-actions { align-items: stretch; flex-direction: column; }
  .detalhe-actions .v-btn { width: 100%; }
}
</style>
