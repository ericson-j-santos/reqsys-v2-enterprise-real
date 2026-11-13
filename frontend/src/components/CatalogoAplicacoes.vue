<template>
  <section class="catalogo-aplicacoes portfolio-card" aria-labelledby="catalogo-aplicacoes-titulo" data-testid="catalogo-aplicacoes">
    <div class="catalogo-cabecalho">
      <div>
        <h2 id="catalogo-aplicacoes-titulo">Inventário de aplicações e sites</h2>
        <p>Fontes verificadas em {{ CATALOGO_VERIFICADO_EM }}. Este registro não substitui o TODO Global nem comprova funcionamento.</p>
      </div>
      <a class="catalogo-referencia" href="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3149"
         target="_blank" rel="noopener noreferrer">Abrir registro oficial da investigação</a>
    </div>
    <p class="catalogo-aviso" role="note">
      Sites publicados podem ser públicos e não têm acesso auditado. Não registre segredos ou dados pessoais neles.
      Status de implantação, existência de código e testes reais são fatos diferentes.
    </p>
    <div class="catalogo-acoes">
      <label for="busca-catalogo-aplicacoes">Buscar aplicação, projeto ou código</label>
      <input id="busca-catalogo-aplicacoes" v-model="buscaCatalogo" type="search"
             autocomplete="off" placeholder="Ex.: continuidade, contratos, host" />
      <span role="status">{{ filtrados.length }} de {{ CATALOGO_APLICACOES.length }} itens identificados; inventário não exaustivo.</span>
    </div>
    <div class="catalogo-tabela-wrap">
      <table class="catalogo-tabela">
        <caption>Inventário de aplicações: fontes de código, links publicados e evidência pendente</caption>
        <thead><tr><th scope="col">Aplicação</th><th scope="col">Fonte / versão</th><th scope="col">Acesso</th><th scope="col">Estado</th><th scope="col">Teste real</th><th scope="col">Responsável e próxima ação</th></tr></thead>
        <tbody>
          <tr v-for="item in filtrados" :key="item.id" data-testid="catalogo-item">
            <td><strong>{{ item.nome }}</strong><small>{{ item.id }} · {{ item.tipo === 'SITE_PUBLICADO' ? 'Site externo' : 'Código identificado' }}</small></td>
            <td>
              <code>{{ item.caminho || 'Versão Git do site não vinculada' }}</code>
              <small>{{ item.gitShaFonte ? 'Fonte Git: ' + item.gitShaFonte.slice(0, 12) : 'SHA da versão publicada não confirmado' }}</small>
              <small v-if="item.versaoPublicada">Versão AppDeploy: {{ item.versaoPublicada }}</small>
            </td>
            <td>
              <a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer"
                 :aria-label="'Abrir site externo ' + item.nome">{{ item.url.replace('https://', '').replace(/\/$/, '') }}</a>
              <span v-else>Sem endereço publicado verificado</span>
              <small>{{ item.acesso === 'ROTA_INTERNA_COM_PERMISSAO' ? 'Rota interna do ReqSys; acesso operacional não testado' : 'Autenticação e permissões não auditadas' }}</small>
            </td>
            <td><span class="catalogo-estado">{{ estadoPorExtenso(item.estado) }}</span><small>{{ ambientePorExtenso(item.ambiente) }}</small></td>
            <td><strong class="catalogo-pendente">{{ item.e2eComprovado ? 'Comprovado' : 'Não comprovado' }}</strong></td>
            <td><strong>{{ item.responsavel }}</strong><small>{{ item.proximaAcao }}</small></td>
          </tr>
          <tr v-if="!filtrados.length"><td colspan="6">Nenhuma aplicação encontrada com esse filtro.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { CATALOGO_APLICACOES, CATALOGO_VERIFICADO_EM, filtrarCatalogoAplicacoes } from '../data/catalogoAplicacoes'

const buscaCatalogo = ref('')
const filtrados = computed(() => filtrarCatalogoAplicacoes(CATALOGO_APLICACOES, buscaCatalogo.value))
function estadoPorExtenso(estado) {
  return ({
    CODIGO_IDENTIFICADO: 'Código identificado',
    BRANCH_IDENTIFICADA: 'Branch identificada',
    PUBLICADO_SEM_E2E: 'Publicado; funcionamento não comprovado',
  })[estado] || 'Sem classificação'
}
function ambientePorExtenso(ambiente) {
  return ambiente === 'PUBLICO_APPDEPLOY' ? 'Publicação AppDeploy (não homologada)' : 'Ambiente não comprovado'
}
</script>

<style scoped>
.catalogo-aplicacoes{display:grid;gap:14px}.catalogo-cabecalho{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.catalogo-cabecalho h2{margin:0}.catalogo-cabecalho p,.catalogo-aplicacoes small{color:var(--muted)}
.catalogo-referencia{align-self:center}.catalogo-aviso{border-left:3px solid #d69c2f;padding:10px 12px;background:rgba(214,156,47,.09);margin:0}
.catalogo-acoes{display:grid;gap:6px}.catalogo-acoes input{width:min(100%,420px);padding:10px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--text)}
.catalogo-acoes span{color:var(--muted)}.catalogo-tabela-wrap{overflow-x:auto}.catalogo-tabela{width:100%;min-width:950px;border-collapse:collapse}
.catalogo-tabela caption{text-align:left;color:var(--muted);padding:8px 0}.catalogo-tabela th,.catalogo-tabela td{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.catalogo-tabela th{white-space:nowrap}.catalogo-tabela td strong,.catalogo-tabela td small{display:block}
.catalogo-tabela code{overflow-wrap:anywhere;white-space:normal}.catalogo-tabela td a{overflow-wrap:anywhere}
.catalogo-pendente{color:#b16c0b}.catalogo-estado{font-weight:600}
</style>
