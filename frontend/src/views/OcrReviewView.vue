<template>
  <main class="ocr-review" data-testid="route-ocr-review" aria-labelledby="ocr-review-title">
    <PageHeader
      id="ocr-review-title"
      title="Revisão humana OCR"
      subtitle="Revise somente resultados que o engine não autorizou como AUTO. PII permanece criptografada em repouso."
    />

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" role="alert">{{ erro }}</v-alert>
    <v-alert v-if="mensagem" type="success" variant="tonal" class="mb-4" role="status">{{ mensagem }}</v-alert>

    <v-card variant="outlined" class="mb-5">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-3">
        <span>Prontidão do OCR</span>
        <v-chip :color="readiness.ready ? 'success' : 'error'" size="small" variant="tonal">
          {{ readiness.ready ? 'Pronto' : 'Bloqueado' }}
        </v-chip>
      </v-card-title>
      <v-card-text>
        <v-progress-linear v-if="carregandoReadiness" indeterminate class="mb-3" />
        <v-row v-else>
          <v-col cols="12" sm="6" md="3">
            <small class="text-medium-emphasis d-block">Criptografia</small>
            <strong>{{ readiness.encryption || '—' }}</strong>
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <small class="text-medium-emphasis d-block">Chave</small>
            <strong>{{ readiness.key_configured ? 'Configurada' : 'Ausente' }}</strong>
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <small class="text-medium-emphasis d-block">OCR input</small>
            <strong>{{ readiness.input_root_configured ? 'Configurado' : 'Ausente' }}</strong>
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <small class="text-medium-emphasis d-block">Engine</small>
            <strong>{{ readiness.engine || '—' }}</strong>
          </v-col>
        </v-row>
        <v-alert v-if="!readiness.ready && !carregandoReadiness" type="warning" variant="tonal" class="mt-3">
          O processamento permanece fail-closed. Configure OCR_DATA_ENCRYPTION_KEY e OCR_INPUT_ROOT antes de enviar documentos.
        </v-alert>
      </v-card-text>
    </v-card>

    <v-card variant="outlined">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-3">
        <span>Fila pendente</span>
        <div class="d-flex ga-2">
          <v-chip size="small" variant="tonal">{{ itens.length }} pendente(s)</v-chip>
          <v-btn variant="text" prepend-icon="mdi-refresh" :loading="carregando" @click="carregar">Atualizar</v-btn>
        </div>
      </v-card-title>
      <v-card-text>
        <v-progress-linear v-if="carregando" indeterminate class="mb-3" />
        <v-alert v-if="!carregando && !itens.length" type="success" variant="tonal">
          Não há resultados aguardando revisão humana.
        </v-alert>
        <v-table v-else density="comfortable">
          <thead>
            <tr>
              <th>Job</th>
              <th>Documento</th>
              <th>Campo</th>
              <th>Estado OCR</th>
              <th>Confiança</th>
              <th>Criado em</th>
              <th class="text-right">Ação</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in itens" :key="item.job_id">
              <td><code>{{ item.job_id }}</code></td>
              <td>{{ item.tipo_documento }}</td>
              <td>{{ item.campo }}</td>
              <td><v-chip size="small" color="warning" variant="tonal">{{ item.estado_ocr }}</v-chip></td>
              <td>{{ percentual(item.confianca) }}</td>
              <td>{{ formatarData(item.criado_em) }}</td>
              <td class="text-right">
                <v-btn size="small" variant="text" prepend-icon="mdi-eye-check-outline" @click="abrir(item)">Revisar</v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-dialog v-model="dialogo" max-width="760" persistent>
      <v-card>
        <v-card-title>Revisar resultado OCR</v-card-title>
        <v-card-text>
          <v-progress-linear v-if="carregandoDetalhe" indeterminate class="mb-4" />
          <template v-else-if="detalhe">
            <v-alert type="warning" variant="tonal" class="mb-4">
              Esta área revela PII somente para decisão humana autenticada. Não copie o conteúdo para logs, issues, PRs ou artifacts públicos.
            </v-alert>
            <v-row class="mb-2">
              <v-col cols="12" md="6"><small class="text-medium-emphasis">Job</small><div><code>{{ detalhe.job_id }}</code></div></v-col>
              <v-col cols="12" md="3"><small class="text-medium-emphasis">Estado</small><div>{{ detalhe.estado_ocr }}</div></v-col>
              <v-col cols="12" md="3"><small class="text-medium-emphasis">Confiança</small><div>{{ percentual(detalhe.confianca) }}</div></v-col>
            </v-row>
            <v-text-field :model-value="detalhe.valor" label="Valor reconhecido" readonly variant="outlined" />
            <v-list v-if="detalhe.motivos?.length" density="compact" class="mb-3">
              <v-list-subheader>Motivos para revisão</v-list-subheader>
              <v-list-item v-for="motivo in detalhe.motivos" :key="motivo" :title="motivo" />
            </v-list>
            <v-textarea v-model.trim="observacao" label="Observação da decisão" maxlength="1000" counter rows="3" />
          </template>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" :disabled="salvando" @click="fechar">Cancelar</v-btn>
          <v-spacer />
          <v-btn color="error" variant="tonal" :loading="salvando && decisaoAtual === 'REJEITADO'" :disabled="carregandoDetalhe" @click="decidir('REJEITADO')">Rejeitar</v-btn>
          <v-btn color="success" :loading="salvando && decisaoAtual === 'APROVADO'" :disabled="carregandoDetalhe" @click="decidir('APROVADO')">Aprovar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import {
  decidirRevisaoOcr,
  detalheErroOcr,
  detalharRevisaoOcr,
  listarRevisoesOcr,
  obterReadinessOcr,
} from '../services/ocrReview'

const readiness = reactive({ ready: false })
const itens = ref([])
const detalhe = ref(null)
const observacao = ref('')
const erro = ref('')
const mensagem = ref('')
const carregando = ref(false)
const carregandoReadiness = ref(false)
const carregandoDetalhe = ref(false)
const salvando = ref(false)
const decisaoAtual = ref('')
const dialogo = ref(false)

function percentual(valor) {
  return `${(Number(valor || 0) * 100).toFixed(2)}%`
}

function formatarData(valor) {
  if (!valor) return '—'
  try { return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(valor)) } catch { return valor }
}

async function carregarReadiness() {
  carregandoReadiness.value = true
  try { Object.assign(readiness, await obterReadinessOcr()) } catch (e) { erro.value = detalheErroOcr(e) } finally { carregandoReadiness.value = false }
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try { itens.value = await listarRevisoesOcr('PENDENTE', 100) } catch (e) { erro.value = detalheErroOcr(e) } finally { carregando.value = false }
}

async function abrir(item) {
  dialogo.value = true
  detalhe.value = null
  observacao.value = ''
  carregandoDetalhe.value = true
  erro.value = ''
  try { detalhe.value = await detalharRevisaoOcr(item.job_id) } catch (e) { erro.value = detalheErroOcr(e); dialogo.value = false } finally { carregandoDetalhe.value = false }
}

function fechar() {
  if (salvando.value) return
  dialogo.value = false
  detalhe.value = null
  observacao.value = ''
}

async function decidir(decisao) {
  if (!detalhe.value?.job_id) return
  decisaoAtual.value = decisao
  salvando.value = true
  erro.value = ''
  try {
    await decidirRevisaoOcr(detalhe.value.job_id, decisao, observacao.value)
    mensagem.value = `Resultado ${decisao === 'APROVADO' ? 'aprovado' : 'rejeitado'} com evidência protegida.`
    fechar()
    await carregar()
  } catch (e) {
    erro.value = detalheErroOcr(e)
  } finally {
    salvando.value = false
    decisaoAtual.value = ''
  }
}

onMounted(async () => {
  await Promise.all([carregarReadiness(), carregar()])
})
</script>
