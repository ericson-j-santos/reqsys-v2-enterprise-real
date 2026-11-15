// Diagnóstico de lacunas de um snapshot do catálogo. Não autentica origens nem executa mutações.
// A conclusão operacional requer readback no backend autorizado; a interface nunca aprova operações.
const SHA = /^[0-9a-f]{40}$/i
const FONTES = ['reqsys', 'todo', 'redmine', 'github', 'runtime']

function texto(valor) {
  return typeof valor === 'string' ? valor.trim() : ''
}

export function analisarLacunasCatalogo(itens) {
  if (!Array.isArray(itens)) throw new TypeError('Catálogo inválido')
  const ids = new Map()
  const urls = new Map()
  for (const item of itens) {
    const id = texto(item?.id)
    if (id) ids.set(id, (ids.get(id) || 0) + 1)
    const url = texto(item?.url)
    if (url) urls.set(url, (urls.get(url) || 0) + 1)
  }
  const registros = itens.map(item => {
    const id = texto(item?.id)
    const avisos = []
    const adicionar = (codigo, explicacao, acao, classe = 'NAO_VERIFICADO') => {
      avisos.push({ codigo, explicacao, acao, classe })
    }

    if (!id) adicionar('ID_NAO_INFORMADO', 'Sem identidade estável no inventário', 'Conferir ID de origem')
    if (id && ids.get(id) > 1) adicionar('ID_REPETIDO_NO_SNAPSHOT', 'ID repetido no inventário recebido', 'Reconciliar identidade antes de outra criação', 'DIVERGENCIA_LOCAL')
    const url = texto(item?.url)
    if (url && urls.get(url) > 1) adicionar('URL_COMPARTILHADA_NO_SNAPSHOT', 'A mesma URL aparece em mais de um registro; pode ser legítimo', 'Comparar finalidade e origem sem excluir', 'SOBREPOSICAO_POTENCIAL')

    const repositorio = texto(item?.repositorio)
    if (!repositorio || repositorio === 'NAO_VINCULADO_A_REPOSITORIO') {
      adicionar('ORIGEM_NAO_VINCULADA', 'O repositório original não está vinculado ao registro', 'Identificar repositório, caminho e versão na origem')
    }
    if (!texto(item?.responsavel)) adicionar('RESPONSAVEL_NAO_VERIFICADO', 'Responsável não registrado', 'Confirmar proprietário do ativo')
    const shaEsperado = texto(item?.shaEsperado)
    const shaConfirmado = texto(item?.shaConfirmado) || texto(item?.gitShaFonte)
    if (shaEsperado && shaConfirmado && SHA.test(shaEsperado) && SHA.test(shaConfirmado) && shaEsperado.toLowerCase() !== shaConfirmado.toLowerCase()) {
      adicionar('SHA_DIVERGENTE_NO_SNAPSHOT', 'Os SHAs esperado e informado diferem neste inventário; confirmar em fonte oficial', 'Suspender promoção e consultar branch/commit e SHA no destino', 'DIVERGENCIA_LOCAL')
    }
    const estadoTodo = texto(item?.todoEstado).toUpperCase().replaceAll('Í', 'I')
    const estadoRedmine = texto(item?.redmineEstado).toUpperCase()
    const estadoGithub = texto(item?.githubEstado).toUpperCase()
    const marcadoConcluido = estado => ['CONCLUIDO', 'CLOSED', 'CLOSED_COMPLETED', 'RESOLVIDO', 'DONE'].includes(estado)
    if (marcadoConcluido(estadoTodo) && (item?.e2eComprovado !== true || !texto(item?.readbackRecibo))) {
      adicionar('TODO_CONCLUIDO_SEM_PROVA', 'O TODO consta concluído no snapshot, mas faltam E2E ou readback', 'Reabrir verificação na fonte canônica; não alterar estado pelo navegador', 'DIVERGENCIA_LOCAL')
    }
    const estadosDeclarados = [estadoTodo, estadoRedmine, estadoGithub].filter(Boolean)
    if (estadosDeclarados.some(marcadoConcluido) && estadosDeclarados.some(e => ['PENDENTE', 'BLOQUEADO', 'EM ANDAMENTO', 'OPEN', 'IN_PROGRESS'].includes(e))) {
      adicionar('ESTADOS_DIVERGENTES_NO_SNAPSHOT', 'Estados informados como concluído e aberto/bloqueado coexistem no snapshot', 'Conferir versões e horários nas fontes antes de sincronizar', 'DIVERGENCIA_LOCAL')
    }
    if (!SHA.test(texto(item?.gitShaFonte))) {
      adicionar('SHA_ORIGEM_NAO_VERIFICADO', 'SHA completo da origem não informado', 'Ler commit da fonte oficial')
    }
    if (url && !texto(item?.versaoPublicada)) adicionar('PUBLICACAO_SEM_VERSAO', 'URL informada sem versão de implantação', 'Consultar versão publicada e conferir SHA no destino')

    // Nenhum vínculo é aceito como prova de sincronização apenas porque está preenchido no frontend.
    if (!texto(item?.todoId)) adicionar('TODO_NAO_VINCULADO', 'Não há vínculo individual com o TODO neste snapshot', 'Localizar o TODO canônico pela chave de idempotência')
    if (!texto(item?.redmineId)) adicionar('REDMINE_NAO_VINCULADO', 'Não há vínculo individual com o Redmine neste snapshot', 'Localizar a demanda já existente no Redmine')
    if (!texto(item?.issue) && !texto(item?.pr)) adicionar('GITHUB_DEMANDA_NAO_VINCULADA', 'Não há issue ou PR individual no registro', 'Conferir vínculos reais e SHA da demanda')
    if (!texto(item?.ciRecibo)) adicionar('CI_SEM_RECIBO_ATUAL', 'Sem resultado de CI comprovado no SHA deste registro', 'Ler checks e artefatos oficiais do commit atual')
    if (item?.e2eComprovado !== true) adicionar('E2E_NAO_COMPROVADO', 'Teste ponta a ponta atual não comprovado', 'Executar teste real positivo, negativo e readback quando autorizado')
    if (!texto(item?.readbackRecibo)) adicionar('READBACK_SEM_RECIBO', 'Sem leitura independente do estado final', 'Confirmar resultado no sistema de destino')

    // Fonte runtime pode ser não aplicável a sites estáticos, mas precisa de decisão documentada.
    if (!texto(item?.aplicabilidadeRuntime)) adicionar('RUNTIME_APLICABILIDADE_NAO_DEFINIDA', 'Execução física e troca de host ainda não classificadas', 'Definir aplicabilidade antes de solicitar canário físico')

    // Divergências explícitas vêm antes das ausências documentais.
    // A classificação é LOCAL: não implica que as fontes remotas estejam inconsistentes.
    const prioridade = { DIVERGENCIA_LOCAL: 0, NAO_VERIFICADO: 1, SOBREPOSICAO_POTENCIAL: 2 }
    avisos.sort((a, b) => (prioridade[a.classe] ?? 9) - (prioridade[b.classe] ?? 9))

    return {
      id: id || 'SEM-ID', nome: texto(item?.nome) || id || 'Sem nome',
      responsavel: texto(item?.responsavel) || 'A confirmar',
      avisos,
      primeiroImpedimento: avisos[0] || null,
      // Nada no navegador, JSON ou snapshot local autentica operação no destino.
      conclusaoOperacionalAutorizada: false,
      fonte: 'INVENTARIO_LOCAL_NAO_AUTENTICADO',
      sistemasRequeridos: FONTES,
      proximaAcao: avisos[0]?.acao || 'Solicitar validação externa independente, vinculada ao SHA e ambiente',
    }
  })
  return {
    fonte: 'SNAPSHOT_LOCAL_NAO_AUTENTICADO',
    total: registros.length,
    semConclusaoOperacional: registros.filter(r => !r.conclusaoOperacionalAutorizada).length,
    comLacunas: registros.filter(r => r.avisos.length > 0).length,
    registros,
    // Não usar contagem de campos documentais como porcentagem de entrega real.
    progressoOperacional: 'NAO_MENSURAVEL_SEM_PROVAS_INDEPENDENTES',
    semMutacaoRemota: true,
  }
}
