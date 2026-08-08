<template>
  <section class="page coleta-page" data-testid="route-coleta-requisitos">
    <div class="page-header">
      <div>
        <div class="eyebrow">ReqSys · Entrada governada</div>
        <h1>Levantar uma nova necessidade</h1>
        <p class="muted coleta-subtitle">
          Descreva o problema, o resultado esperado e os critérios verificáveis. O ReqSys avalia a qualidade antes de gerar o requisito.
        </p>
      </div>
      <div class="header-actions">
        <v-btn variant="outlined" prepend-icon="mdi-format-list-bulleted" to="/requisitos">
          Ver requisitos
        </v-btn>
        <v-chip v-if="contrato" color="blue" variant="tonal" size="small">
          Contrato {{ contrato.versao_contrato }}
        </v-chip>
      </div>
    </div>

    <v-alert v-if="erroContrato" type="error" variant="tonal" class="mb-4" data-testid="erro-contrato">
      {{ erroContrato }}
      <template #append>
        <v-btn size="small" variant="text" @click="carregarContrato">Tentar novamente</v-btn>
      </template>
    </v-alert>

    <v-skeleton-loader v-if="carregandoContrato" type="article, article, article" />

    <template v-else-if="contrato">
      <v-row class="mb-4">
        <v-col cols="12" md="8">
          <v-alert type="info" variant="tonal" icon="mdi-information-outline">
            {{ contrato.objetivo }}
          </v-alert>
        </v-col>
        <v-col cols="12" md="4">
          <v-card class="quality-card" elevation="0">
            <div class="quality-card__header">
              <span class="muted">Qualidade da coleta</span>
              <strong data-testid="pontuacao-coleta">{{ avaliacao?.pontuacao ?? '—' }}</strong>
            </div>
            <v-progress-linear
              :model-value="avaliacao?.pontuacao ?? 0"
              :color="corPontuacao"
              height="8"
              rounded
              class="mt-2"
            />
            <div class="muted quality-card__footer">
              Mínimo para gerar: {{ contrato.regra_geracao.pontuacao_minima }} pontos
            </div>
          </v-card>
        </v-col>
      </v-row>

      <v-alert type="warning" variant="tonal" class="mb-4" icon="mdi-shield-lock-outline">
        Não informe senhas, tokens, segredos, chaves de acesso ou dados pessoais desnecessários. Para evidências e anexos, use referência corporativa governada.
      </v-alert>

      <form @submit.prevent="previsualizar" novalidate>
        <v-card
          v-for="(secao, indice) in secoes"
          :key="secao.id"
          class="section-card mb-4"
          elevation="0"
          :data-testid="`secao-${secao.id}`"
        >
          <v-card-title class="section-title">
            <span class="section-index">{{ indice + 1 }}</span>
            <span>{{ secao.titulo }}</span>
          </v-card-title>
          <v-card-text>
            <v-row>
              <v-col
                v-for="campo in secao.campos"
                :key="campo.nome"
                cols="12"
                :md="campo.largura || 12"
              >
                <v-select
                  v-if="campo.tipo === 'selecao'"
                  v-model="formulario[campo.nome]"
                  :label="campo.rotulo"
                  :items="campo.opcoes"
                  variant="outlined"
                  density="comfortable"
                  :hint="campo.ajuda"
                  persistent-hint
                  :required="campo.obrigatorio"
                  :data-testid="`campo-${campo.nome}`"
                />

                <v-switch
                  v-else-if="campo.tipo === 'booleano'"
                  v-model="formulario[campo.nome]"
                  :label="campo.rotulo"
                  color="amber"
                  inset
                  :hint="campo.ajuda"
                  persistent-hint
                  :data-testid="`campo-${campo.nome}`"
                />

                <v-textarea
                  v-else-if="campo.tipo === 'texto_longo' || campo.tipo === 'lista'"
                  v-model="formulario[campo.nome]"
                  :label="campo.rotulo"
                  variant="outlined"
                  :rows="campo.linhas || 3"
                  auto-grow
                  :hint="campo.ajuda"
                  persistent-hint
                  :required="campo.obrigatorio"
                  :data-testid="`campo-${campo.nome}`"
                />

                <v-text-field
                  v-else
                  v-model="formulario[campo.nome]"
                  :label="campo.rotulo"
                  variant="outlined"
                  :type="campo.tipo === 'data' ? 'date' : 'text'"
                  :hint="campo.ajuda"
                  persistent-hint
                  :required="campo.obrigatorio"
                  :data-testid="`campo-${campo.nome}`"
                />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <v-alert v-if="erroOperacao" type="error" variant="tonal" class="mb-4" data-testid="erro-operacao">
          {{ erroOperacao }}
        </v-alert>

        <v-expand-transition>
          <v-card v-if="avaliacao" class="resultado-card mb-4" elevation="0" data-testid="resultado-avaliacao">
            <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
              <span>Resultado da avaliação</span>
              <v-chip :color="corPontuacao" variant="tonal">
                {{ avaliacao.classificacao }} · {{ avaliacao.pontuacao }}/100
              </v-chip>
            </v-card-title>
            <v-card-text>
              <v-alert
                :type="avaliacao.pronto_para_gerar ? 'success' : 'warning'"
                variant="tonal"
                class="mb-3"
              >
                {{ avaliacao.pronto_para_gerar
                  ? 'A coleta atingiu o nível mínimo e pode gerar um requisito.'
                  : 'A coleta precisa de refinamento antes da geração do requisito.' }}
              </v-alert>

              <div v-if="avaliacao.pendencias?.length" class="mb-4">
                <strong>Pendências objetivas</strong>
                <ul class="mt-2">
                  <li v-for="item in avaliacao.pendencias" :key="item">{{ item }}</li>
                </ul>
              </div>

              <div v-if="avaliacao.alertas?.length">
                <strong>Alertas</strong>
                <ul class="mt-2">
                  <li v-for="item in avaliacao.alertas" :key="item">{{ item }}</li>
                </ul>
              </div>
            </v-card-text>
          </v-card>
        </v-expand-transition>

        <v-expand-transition>
          <v-alert v-if="requisitoGerado" type="success" variant="tonal" class="mb-4" data-testid="requisito-gerado">
            <strong>{{ requisitoGerado.codigo }}</strong> — {{ requisitoGerado.titulo }}
            <div class="mt-2">
              <v-btn size="small" variant="outlined" to="/requisitos">Abrir lista de requisitos</v-btn>
            </div>
          </v-alert>
        </v-expand-transition>

        <div class="actions-bar">
          <v-btn variant="text" :disabled="ocupado" @click="reiniciar">Limpar</v-btn>
          <v-spacer />
          <v-btn
            type="submit"
            variant="outlined"
            prepend-icon="mdi-clipboard-check-outline"
            :loading="previsualizando"
            :disabled="gerando"
            data-testid="acao-previsualizar"
          >
            Avaliar coleta
          </v-btn>
          <v-btn
            color="amber"
            prepend-icon="mdi-file-document-plus-outline"
            :loading="gerando"
            :disabled="!avaliacao?.pronto_para_gerar || previsualizando"
            data-testid="acao-gerar"
            @click="gerar"
          >
            Gerar requisito
          </v-btn>
        </div>
      </form>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../services/api'

const carregandoContrato = ref(true)
const previsualizando = ref(false)
const gerando = ref(false)
const erroContrato = ref('')
const erroOperacao = ref('')
const contrato = ref(null)
const avaliacao = ref(null)
const requisitoGerado = ref(null)

const CAMPOS_LISTA = new Set([
  'regras_negocio',
  'criterios_aceite',
  'dados_necessarios',
  'integracoes',
  'restricoes',
])

const DEFINICOES = {
  solicitante: {
    rotulo: 'Solicitante', tipo: 'texto', largura: 4, obrigatorio: true,
    ajuda: 'Pessoa, papel ou equipe que responde pela necessidade.',
  },
  area: {
    rotulo: 'Área', tipo: 'texto', largura: 4, obrigatorio: true,
    ajuda: 'Área de negócio ou técnica responsável pela demanda.',
  },
  sistema: {
    rotulo: 'Sistema, produto ou processo afetado', tipo: 'texto', largura: 4, obrigatorio: true,
    ajuda: 'Informe o principal contexto afetado pela necessidade.',
  },
  tipo_demanda: {
    rotulo: 'Tipo de demanda', tipo: 'selecao', largura: 6, obrigatorio: true,
    ajuda: 'Classificação inicial para triagem e rastreabilidade.',
  },
  origem: {
    rotulo: 'Origem', tipo: 'selecao', largura: 6, obrigatorio: true,
    ajuda: 'Canal pelo qual a informação foi coletada.',
  },
  referencia_externa: {
    rotulo: 'Referência externa', tipo: 'texto', largura: 12, obrigatorio: false,
    ajuda: 'Chamado, épico, norma, política ou outra referência rastreável. Obrigatória para impacto regulatório.',
  },
  problema: {
    rotulo: 'Qual problema existe hoje?', tipo: 'texto_longo', linhas: 4, obrigatorio: true,
    ajuda: 'Descreva causa, impacto e contexto. Evite começar pela solução desejada.',
  },
  objetivo: {
    rotulo: 'Qual resultado precisa ser alcançado?', tipo: 'texto_longo', linhas: 3, obrigatorio: true,
    ajuda: 'Explique o resultado de negócio ou operacional esperado.',
  },
  usuario_afetado: {
    rotulo: 'Quem é afetado?', tipo: 'texto', largura: 12, obrigatorio: true,
    ajuda: 'Perfil de usuário, papel, equipe ou área impactada.',
  },
  processo_atual: {
    rotulo: 'Como funciona atualmente?', tipo: 'texto_longo', linhas: 3, obrigatorio: false,
    ajuda: 'Descreva o fluxo atual ou declare explicitamente que ele não existe.',
  },
  cenario_desejado: {
    rotulo: 'Como deve funcionar no cenário desejado?', tipo: 'texto_longo', linhas: 4, obrigatorio: true,
    ajuda: 'Descreva o comportamento futuro sem limitar desnecessariamente a solução técnica.',
  },
  regras_negocio: {
    rotulo: 'Regras de negócio', tipo: 'lista', linhas: 4, obrigatorio: false,
    ajuda: 'Uma regra por linha. Se não houver, escreva uma declaração explícita para isso.',
  },
  criterios_aceite: {
    rotulo: 'Critérios de aceite', tipo: 'lista', linhas: 5, obrigatorio: true,
    ajuda: 'Um critério verificável por linha. Recomenda-se informar pelo menos dois.',
  },
  impacto_regulatorio: {
    rotulo: 'Há impacto regulatório, normativo ou de auditoria?', tipo: 'booleano', largura: 12, obrigatorio: false,
    ajuda: 'Quando marcado, a referência externa rastreável torna-se obrigatória.',
  },
  dados_necessarios: {
    rotulo: 'Dados necessários', tipo: 'lista', linhas: 3, obrigatorio: false,
    ajuda: 'Um dado ou conjunto de dados por linha.',
  },
  integracoes: {
    rotulo: 'Integrações e dependências', tipo: 'lista', linhas: 3, obrigatorio: false,
    ajuda: 'Uma API, fila, arquivo, serviço ou sistema por linha.',
  },
  restricoes: {
    rotulo: 'Restrições', tipo: 'lista', linhas: 3, obrigatorio: false,
    ajuda: 'Uma restrição técnica, operacional, segurança ou acesso por linha.',
  },
  urgencia: {
    rotulo: 'Urgência', tipo: 'selecao', largura: 6, obrigatorio: true,
    ajuda: 'Use criticidade real; prazo externo deve ser informado separadamente.',
  },
  data_limite: {
    rotulo: 'Data limite externa', tipo: 'data', largura: 6, obrigatorio: false,
    ajuda: 'Preencha apenas quando houver uma data externa real e justificável.',
  },
  observacoes: {
    rotulo: 'Observações adicionais', tipo: 'texto_longo', linhas: 3, obrigatorio: false,
    ajuda: 'Contexto adicional que não se encaixa nos campos anteriores.',
  },
}

const estadoInicial = () => ({
  chave_idempotencia: gerarChaveIdempotencia(),
  origem: 'reqsys',
  solicitante: '',
  area: '',
  sistema: '',
  tipo_demanda: 'nova_funcionalidade',
  problema: '',
  objetivo: '',
  usuario_afetado: '',
  processo_atual: '',
  cenario_desejado: '',
  regras_negocio: '',
  criterios_aceite: '',
  dados_necessarios: '',
  integracoes: '',
  restricoes: '',
  impacto_regulatorio: false,
  urgencia: 'media',
  data_limite: '',
  referencia_externa: '',
  observacoes: '',
})

const formulario = reactive(estadoInicial())

const ocupado = computed(() => carregandoContrato.value || previsualizando.value || gerando.value)

const secoes = computed(() => {
  if (!contrato.value?.secoes) return []
  return contrato.value.secoes.map((secao) => ({
    ...secao,
    campos: secao.campos
      .map((nome) => {
        const definicao = DEFINICOES[nome]
        if (!definicao) return null
        const opcoes = contrato.value?.opcoes?.[nome] || []
        return { nome, ...definicao, opcoes }
      })
      .filter(Boolean),
  }))
})

const corPontuacao = computed(() => {
  const score = avaliacao.value?.pontuacao ?? 0
  if (score >= 90) return 'green'
  if (score >= 80) return 'blue'
  if (score >= 60) return 'amber'
  return 'red'
})

onMounted(carregarContrato)

function gerarChaveIdempotencia() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `reqsys-${crypto.randomUUID()}`
  }
  return `reqsys-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function converterLista(valor) {
  return String(valor || '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function limparNulo(valor) {
  const texto = String(valor || '').trim()
  return texto || null
}

function construirPayload() {
  const payload = {
    versao_contrato: contrato.value?.versao_contrato || '1.0.0',
    ...formulario,
    processo_atual: limparNulo(formulario.processo_atual),
    data_limite: limparNulo(formulario.data_limite),
    referencia_externa: limparNulo(formulario.referencia_externa),
    observacoes: limparNulo(formulario.observacoes),
  }
  CAMPOS_LISTA.forEach((nome) => {
    payload[nome] = converterLista(formulario[nome])
  })
  return payload
}

async function carregarContrato() {
  carregandoContrato.value = true
  erroContrato.value = ''
  try {
    const resposta = await api.get('/requisitos/coleta/formulario')
    contrato.value = resposta.data?.data
    if (!contrato.value?.versao_contrato || !Array.isArray(contrato.value?.secoes)) {
      throw new Error('Contrato de coleta inválido ou incompleto.')
    }
  } catch (erro) {
    contrato.value = null
    erroContrato.value = erro?.response?.data?.detail?.message || erro?.message || 'Não foi possível carregar o contrato de coleta.'
  } finally {
    carregandoContrato.value = false
  }
}

async function previsualizar() {
  erroOperacao.value = ''
  requisitoGerado.value = null
  previsualizando.value = true
  try {
    const resposta = await api.post('/requisitos/coleta/previsualizar', construirPayload())
    avaliacao.value = resposta.data?.data?.avaliacao || null
  } catch (erro) {
    avaliacao.value = null
    erroOperacao.value = extrairErro(erro, 'Não foi possível avaliar a coleta.')
  } finally {
    previsualizando.value = false
  }
}

async function gerar() {
  if (!avaliacao.value?.pronto_para_gerar) return
  erroOperacao.value = ''
  gerando.value = true
  try {
    const resposta = await api.post('/requisitos/coleta/gerar', construirPayload())
    const dados = resposta.data?.data
    avaliacao.value = dados?.avaliacao || avaliacao.value
    requisitoGerado.value = dados?.requisito || null
    if (!requisitoGerado.value?.codigo) {
      throw new Error('A API não retornou o requisito persistido.')
    }
  } catch (erro) {
    erroOperacao.value = extrairErro(erro, 'Não foi possível gerar o requisito.')
    const avaliacaoErro = erro?.response?.data?.detail
    if (avaliacaoErro?.pontuacao !== undefined) {
      avaliacao.value = {
        pontuacao: avaliacaoErro.pontuacao,
        classificacao: 'refinamento',
        pronto_para_gerar: false,
        pendencias: avaliacaoErro.pendencias || [],
        alertas: avaliacaoErro.alertas || [],
      }
    }
  } finally {
    gerando.value = false
  }
}

function extrairErro(erro, padrao) {
  const detalhe = erro?.response?.data?.detail
  if (typeof detalhe === 'string') return detalhe
  if (detalhe?.message) return detalhe.message
  if (Array.isArray(detalhe)) {
    return detalhe.map((item) => item?.msg).filter(Boolean).join('; ') || padrao
  }
  return erro?.message || padrao
}

function reiniciar() {
  Object.assign(formulario, estadoInicial())
  avaliacao.value = null
  requisitoGerado.value = null
  erroOperacao.value = ''
}
</script>

<style scoped>
.coleta-subtitle { max-width: 72ch; }
.eyebrow { font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); margin-bottom: 4px; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.quality-card { height: 100%; padding: 16px; border: 1px solid rgba(148, 163, 184, .25); }
.quality-card__header { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.quality-card__header strong { font-size: 28px; }
.quality-card__footer { font-size: 12px; margin-top: 8px; }
.section-card, .resultado-card { border: 1px solid rgba(148, 163, 184, .22); }
.section-title { display: flex; align-items: center; gap: 10px; }
.section-index { width: 28px; height: 28px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; background: rgba(245, 158, 11, .16); color: var(--accent); font-size: 13px; font-weight: 800; }
.actions-bar { position: sticky; bottom: 12px; z-index: 3; display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 14px; background: rgba(15, 23, 42, .94); border: 1px solid rgba(148, 163, 184, .25); backdrop-filter: blur(12px); }
ul { padding-left: 22px; }
@media (max-width: 700px) {
  .actions-bar { flex-wrap: wrap; }
  .actions-bar .v-btn { flex: 1 1 auto; }
}
</style>
