<template>
  <main class="recipient-policies" data-testid="route-teams-recipient-policies" aria-labelledby="recipient-policies-title">
    <PageHeader
      id="recipient-policies-title"
      title="Políticas de destinatários Teams"
      subtitle="Administre aprovadores e operadores com dry-run, mascaramento de identidade e acesso restrito."
    />

    <v-alert type="info" variant="tonal" class="mb-4">
      Esta tela administra somente metadados de destinatários. Tokens, secrets e credenciais de integração não são exibidos nem armazenados aqui.
    </v-alert>
    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" role="alert">{{ erro }}</v-alert>
    <v-alert v-if="mensagem" type="success" variant="tonal" class="mb-4" role="status">{{ mensagem }}</v-alert>

    <v-card variant="outlined" class="mb-5" data-testid="teams-graph-identity-status">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-3">
        <span>Application Teams Graph</span>
        <v-chip :color="corStatusIdentidade" size="small" variant="tonal">
          {{ textoStatusIdentidade }}
        </v-chip>
      </v-card-title>
      <v-card-text>
        <v-progress-linear v-if="carregandoIdentidade" indeterminate class="mb-3" />
        <v-alert v-else-if="erroIdentidade" type="error" variant="tonal" class="mb-3">
          {{ erroIdentidade }}
        </v-alert>
        <template v-else-if="identidadeTeams">
          <v-alert v-if="!identidadeTeams.configured" type="error" variant="tonal" class="mb-3">
            {{ identidadeTeams.error || 'A Application do Teams Graph não está disponível para este ambiente.' }}
          </v-alert>
          <template v-else>
            <v-row class="mb-2">
              <v-col cols="12" sm="6" md="3">
                <small class="text-medium-emphasis d-block">Perfil</small>
                <strong>{{ identidadeTeams.profile_name }}</strong>
              </v-col>
              <v-col cols="12" sm="6" md="3">
                <small class="text-medium-emphasis d-block">Ambiente</small>
                <strong>{{ identidadeTeams.environment }}</strong>
              </v-col>
              <v-col cols="12" sm="6" md="3">
                <small class="text-medium-emphasis d-block">Client ID</small>
                <code>••••{{ identidadeTeams.client_id_suffix }}</code>
              </v-col>
              <v-col cols="12" sm="6" md="3">
                <small class="text-medium-emphasis d-block">Próxima rotação</small>
                <strong>{{ formatarDataIdentidade(identidadeTeams.rotation_due_at) }}</strong>
              </v-col>
            </v-row>
            <v-alert :type="identidadeTeams.rotation_required ? 'warning' : 'success'" variant="tonal" class="mb-3">
              {{ identidadeTeams.rotation_required
                ? 'A credencial atual precisa ser rotacionada antes de novos envios app-only.'
                : 'A credencial atual está dentro da janela de rotação.' }}
            </v-alert>
          </template>
        </template>
        <v-btn
          variant="text"
          prepend-icon="mdi-refresh"
          :loading="carregandoIdentidade"
          @click="carregarIdentidade"
        >
          Atualizar status
        </v-btn>
      </v-card-text>
    </v-card>

    <v-row class="mb-2">
      <v-col v-for="politica in politicas" :key="politica.id" cols="12" md="6">
        <v-card variant="outlined" class="h-100">
          <v-card-title class="d-flex align-center justify-space-between ga-3">
            <span>{{ politica.titulo }}</span>
            <v-chip :color="corReadiness(politica.id)" size="small" variant="tonal">
              {{ textoReadiness(politica.id) }}
            </v-chip>
          </v-card-title>
          <v-card-text>
            <p class="mb-3">{{ politica.descricao }}</p>
            <div class="d-flex ga-2 flex-wrap">
              <v-chip size="small" variant="outlined">{{ membrosAtivos(politica.id) }} ativos</v-chip>
              <v-chip size="small" variant="outlined">{{ membrosDaPolitica(politica.id).length }} cadastrados</v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card variant="outlined" class="mb-5">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-3">
        <span>Destinatários cadastrados</span>
        <v-btn color="primary" prepend-icon="mdi-account-plus" @click="abrirNovo">Adicionar membro</v-btn>
      </v-card-title>
      <v-card-text>
        <v-select
          v-model="politicaSelecionada"
          label="Política"
          :items="politicas"
          item-title="titulo"
          item-value="id"
          class="mb-3"
          hide-details
        />

        <v-progress-linear v-if="carregando" indeterminate class="mb-3" />
        <v-alert v-if="!carregando && !membrosDaPolitica(politicaSelecionada).length" type="warning" variant="tonal">
          Nenhum destinatário cadastrado nesta política. A readiness permanecerá fail-closed até existir ao menos um membro ativo e o dry-run ser aprovado.
        </v-alert>

        <v-table v-else density="comfortable">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Destino</th>
              <th>Tipo</th>
              <th>Prioridade</th>
              <th>Status</th>
              <th class="text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in membrosDaPolitica(politicaSelecionada)" :key="item.id">
              <td>{{ item.nome || 'Sem nome' }}</td>
              <td><code>{{ mascararDestino(item.destino_id) }}</code></td>
              <td>{{ item.destino_tipo }}</td>
              <td>{{ item.prioridade }}</td>
              <td>
                <v-chip :color="item.ativo ? 'success' : 'default'" size="small" variant="tonal">
                  {{ item.ativo ? 'Ativo' : 'Inativo' }}
                </v-chip>
              </td>
              <td class="text-right">
                <v-btn icon="mdi-pencil" variant="text" size="small" title="Editar membro" @click="abrirEdicao(item)" />
                <v-btn
                  :icon="item.ativo ? 'mdi-account-off-outline' : 'mdi-account-check-outline'"
                  variant="text"
                  size="small"
                  :title="item.ativo ? 'Desativar membro' : 'Ativar membro'"
                  @click="alternarAtivo(item)"
                />
                <v-btn icon="mdi-delete-outline" color="error" variant="text" size="small" title="Remover membro" @click="confirmarRemocao(item)" />
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-card variant="outlined">
      <v-card-title>Readiness governada</v-card-title>
      <v-card-text>
        <p class="mb-4">
          Executa dry-run para as duas políticas canônicas. Nenhuma mensagem real deve ser enviada e o fallback explícito permanece proibido durante a prova.
        </p>
        <v-row>
          <v-col v-for="politica in politicas" :key="`readiness-${politica.id}`" cols="12" md="6">
            <v-card variant="tonal" class="pa-4 h-100">
              <div class="d-flex align-center justify-space-between ga-3">
                <strong>{{ politica.titulo }}</strong>
                <v-chip :color="corReadiness(politica.id)" size="small">{{ textoReadiness(politica.id) }}</v-chip>
              </div>
              <small v-if="readiness[politica.id]?.correlationId" class="d-block mt-2">
                correlation_id: <code>{{ readiness[politica.id].correlationId }}</code>
              </small>
              <small v-if="readiness[politica.id]?.erro" class="d-block mt-2 text-error">{{ readiness[politica.id].erro }}</small>
            </v-card>
          </v-col>
        </v-row>
        <v-alert class="my-4" :type="readinessGeral.tipo" variant="tonal">
          {{ readinessGeral.texto }}
        </v-alert>
        <v-btn color="primary" prepend-icon="mdi-shield-check-outline" :loading="validandoReadiness" @click="executarReadinessCompleta">
          Executar dry-run das duas políticas
        </v-btn>
      </v-card-text>
    </v-card>

    <v-dialog v-model="dialogoEdicao" max-width="640">
      <v-card>
        <v-card-title>{{ formulario.id ? 'Editar membro' : 'Adicionar membro' }}</v-card-title>
        <v-card-text>
          <v-select v-model="formulario.politica" label="Política" :items="politicas" item-title="titulo" item-value="id" />
          <v-text-field v-model.trim="formulario.nome" label="Nome de exibição" maxlength="200" />
          <v-text-field
            v-model.trim="formulario.destino_id"
            label="Identificador do destinatário"
            maxlength="500"
            hint="Informe somente nesta tela administrativa. O valor ficará mascarado na listagem."
            persistent-hint
          />
          <v-select v-model="formulario.destino_tipo" label="Tipo de destino" :items="tiposDestino" />
          <v-text-field v-model.number="formulario.prioridade" label="Prioridade" type="number" min="0" max="100000" />
          <v-switch v-model="formulario.ativo" label="Membro ativo" color="primary" />
          <v-textarea v-model.trim="formulario.observacao" label="Observação" maxlength="500" rows="2" />
          <v-alert type="warning" variant="tonal" density="compact">
            Não copie e-mail, UPN ou identificadores individuais para issues, PRs, logs ou artifacts públicos.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialogoEdicao = false">Cancelar</v-btn>
          <v-btn color="primary" :loading="salvando" :disabled="!formularioValido" @click="salvar">Salvar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="dialogoRemocao" max-width="520">
      <v-card>
        <v-card-title>Confirmar remoção</v-card-title>
        <v-card-text>
          Remover <strong>{{ itemRemocao?.nome || 'este membro' }}</strong> da política
          <code>{{ itemRemocao?.politica }}</code>? A readiness poderá voltar para estado bloqueado.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialogoRemocao = false">Cancelar</v-btn>
          <v-btn color="error" :loading="removendo" @click="remover">Remover</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import { obterStatusIdentidadeTeamsGateway } from '../services/teamsGateway'
import {
  POLITICAS_TEAMS_CANONICAS,
  atualizarDestinatario,
  criarDestinatario,
  detalheErroPolitica,
  executarReadiness,
  listarDestinatarios,
  mascararDestino,
  removerDestinatario,
} from '../services/teamsRecipientPolicies'

const politicas = POLITICAS_TEAMS_CANONICAS
const tiposDestino = ['chat', 'canal', 'webhook', 'auto']
const politicaSelecionada = ref(politicas[0].id)
const membros = ref([])
const readiness = reactive({})
const carregando = ref(false)
const carregandoIdentidade = ref(false)
const identidadeTeams = ref(null)
const erroIdentidade = ref('')
const salvando = ref(false)
const removendo = ref(false)
const validandoReadiness = ref(false)
const erro = ref('')
const mensagem = ref('')
const dialogoEdicao = ref(false)
const dialogoRemocao = ref(false)
const itemRemocao = ref(null)

const formularioInicial = () => ({
  id: null,
  politica: politicaSelecionada.value,
  nome: '',
  destino_id: '',
  destino_tipo: 'chat',
  prioridade: 100,
  ativo: true,
  observacao: '',
})
const formulario = reactive(formularioInicial())

const formularioValido = computed(() => Boolean(
  formulario.politica &&
  formulario.destino_id?.trim()?.length >= 2 &&
  Number(formulario.prioridade) >= 0,
))

const textoStatusIdentidade = computed(() => {
  if (carregandoIdentidade.value) return 'Consultando'
  if (erroIdentidade.value || !identidadeTeams.value?.configured) return 'Bloqueada'
  return identidadeTeams.value.rotation_required ? 'Rotação necessária' : 'Ativa'
})

const corStatusIdentidade = computed(() => {
  if (erroIdentidade.value || !identidadeTeams.value?.configured) return 'error'
  return identidadeTeams.value.rotation_required ? 'warning' : 'success'
})

const readinessGeral = computed(() => {
  const resultados = politicas.map((p) => readiness[p.id]).filter(Boolean)
  if (!resultados.length) return { tipo: 'info', texto: 'Prontidão ainda não executada nesta sessão.' }
  if (resultados.length < politicas.length) return { tipo: 'warning', texto: 'Prontidão parcial. Execute a validação completa das duas políticas.' }
  const prontos = resultados.filter((item) => item.pronto).length
  if (prontos === politicas.length) {
    return { tipo: 'success', texto: `2/2 políticas READY. Candidato a retirar o fallback legado após a governança prevista.` }
  }
  return { tipo: 'error', texto: `${prontos}/2 políticas READY. Mantenha o fallback legado e corrija os bloqueios antes de promover.` }
})

function formatarDataIdentidade(valor) {
  if (!valor) return 'Não informado'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return 'Data inválida'
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(data)
}

function membrosDaPolitica(politica) {
  return membros.value.filter((item) => item.politica === politica)
}

function membrosAtivos(politica) {
  return membrosDaPolitica(politica).filter((item) => item.ativo).length
}

function textoReadiness(politica) {
  const estado = readiness[politica]
  if (!estado) return membrosAtivos(politica) ? 'Não validado' : 'Bloqueado'
  return estado.pronto ? 'READY' : 'BLOQUEADO'
}

function corReadiness(politica) {
  const estado = readiness[politica]
  if (!estado) return membrosAtivos(politica) ? 'warning' : 'error'
  return estado.pronto ? 'success' : 'error'
}

function limparFeedback() {
  erro.value = ''
  mensagem.value = ''
}

async function carregarIdentidade() {
  carregandoIdentidade.value = true
  erroIdentidade.value = ''
  try {
    identidadeTeams.value = await obterStatusIdentidadeTeamsGateway()
  } catch (error) {
    identidadeTeams.value = null
    erroIdentidade.value = detalheErroPolitica(error)
  } finally {
    carregandoIdentidade.value = false
  }
}

async function carregar() {
  carregando.value = true
  limparFeedback()
  try {
    const lotes = await Promise.all(politicas.map((p) => listarDestinatarios(p.id, false)))
    membros.value = lotes.flat()
  } catch (error) {
    erro.value = detalheErroPolitica(error)
  } finally {
    carregando.value = false
  }
}

function abrirNovo() {
  Object.assign(formulario, formularioInicial())
  dialogoEdicao.value = true
}

function abrirEdicao(item) {
  Object.assign(formulario, {
    id: item.id,
    politica: item.politica,
    nome: item.nome || '',
    destino_id: item.destino_id || '',
    destino_tipo: item.destino_tipo || 'chat',
    prioridade: item.prioridade ?? 100,
    ativo: Boolean(item.ativo),
    observacao: item.observacao || '',
  })
  dialogoEdicao.value = true
}

async function salvar() {
  salvando.value = true
  limparFeedback()
  const payload = {
    politica: formulario.politica,
    nome: formulario.nome,
    destino_id: formulario.destino_id,
    destino_tipo: formulario.destino_tipo,
    prioridade: Number(formulario.prioridade),
    ativo: Boolean(formulario.ativo),
    observacao: formulario.observacao,
  }
  try {
    if (formulario.id) {
      const { politica, ...updatePayload } = payload
      await atualizarDestinatario(formulario.id, updatePayload)
    } else {
      await criarDestinatario(payload)
    }
    dialogoEdicao.value = false
    mensagem.value = 'Cadastro atualizado com sucesso. Execute novamente a prontidão antes de alterar qualquer fallback.'
    Object.keys(readiness).forEach((key) => delete readiness[key])
    await carregar()
  } catch (error) {
    erro.value = detalheErroPolitica(error)
  } finally {
    salvando.value = false
  }
}

async function alternarAtivo(item) {
  limparFeedback()
  try {
    await atualizarDestinatario(item.id, { ativo: !item.ativo })
    Object.keys(readiness).forEach((key) => delete readiness[key])
    await carregar()
    mensagem.value = item.ativo ? 'Membro desativado.' : 'Membro ativado. Execute a prontidão novamente.'
  } catch (error) {
    erro.value = detalheErroPolitica(error)
  }
}

function confirmarRemocao(item) {
  itemRemocao.value = item
  dialogoRemocao.value = true
}

async function remover() {
  if (!itemRemocao.value) return
  removendo.value = true
  limparFeedback()
  try {
    await removerDestinatario(itemRemocao.value.id)
    dialogoRemocao.value = false
    itemRemocao.value = null
    Object.keys(readiness).forEach((key) => delete readiness[key])
    await carregar()
    mensagem.value = 'Membro removido. A prontidão foi invalidada e precisa ser executada novamente.'
  } catch (error) {
    erro.value = detalheErroPolitica(error)
  } finally {
    removendo.value = false
  }
}

async function executarReadinessCompleta() {
  validandoReadiness.value = true
  limparFeedback()
  try {
    const resultados = await Promise.all(politicas.map((p) => executarReadiness(p.id)))
    resultados.forEach((resultado) => { readiness[resultado.politica] = resultado })
    const prontos = resultados.filter((item) => item.pronto).length
    mensagem.value = prontos === politicas.length
      ? 'Prontidão concluída: 2/2 políticas READY, sem fallback explícito.'
      : `Prontidão concluída: ${prontos}/${politicas.length} políticas READY.`
  } catch (error) {
    erro.value = detalheErroPolitica(error)
  } finally {
    validandoReadiness.value = false
  }
}

onMounted(() => {
  carregar()
  carregarIdentidade()
})
</script>

<style scoped>
.recipient-policies { max-width: 1180px; margin: 0 auto; padding: var(--space-xl); }
code { overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .recipient-policies { padding: var(--space-lg); }
}
</style>