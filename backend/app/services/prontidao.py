from app.schemas.processos import (
    ContextoAntecipacao,
    ItemValidacao,
    ResultadoAntecipacao,
    Severidade,
    TipoProcesso,
)


def antecipar_validacoes(contexto: ContextoAntecipacao) -> ResultadoAntecipacao:
    bloqueios: list[ItemValidacao] = []
    alertas: list[ItemValidacao] = []
    pendencias: list[str] = []

    validar_campos_obrigatorios(contexto, bloqueios, pendencias)
    validar_permissao_usuario(contexto, bloqueios)
    validar_evidencias(contexto, bloqueios, alertas, pendencias)
    validar_regras_por_tipo(contexto, bloqueios, alertas, pendencias)

    score_prontidao = calcular_score_prontidao(bloqueios, alertas, pendencias)

    if bloqueios:
        status = "bloqueado"
        apto = False
    elif alertas or pendencias:
        status = "aprovado_com_alerta"
        apto = True
    else:
        status = "aprovado"
        apto = True

    return ResultadoAntecipacao(
        apto_para_iniciar=apto,
        status_validacao=status,
        score_prontidao=score_prontidao,
        bloqueios=bloqueios,
        alertas=alertas,
        pendencias=pendencias,
        correlation_id=contexto.correlation_id,
    )


def validar_campos_obrigatorios(
    contexto: ContextoAntecipacao,
    bloqueios: list[ItemValidacao],
    pendencias: list[str],
) -> None:
    dados = contexto.dados

    campos_obrigatorios = {
        "titulo": "Título é obrigatório.",
        "descricao": "Descrição é obrigatória.",
        "responsavel": "Responsável é obrigatório.",
        "prioridade": "Prioridade é obrigatória.",
    }

    for campo, mensagem in campos_obrigatorios.items():
        valor = dados.get(campo)
        if valor is None or str(valor).strip() == "":
            bloqueios.append(
                ItemValidacao(
                    codigo="CAMPO_OBRIGATORIO_AUSENTE",
                    mensagem=mensagem,
                    campo=f"dados.{campo}",
                    severidade=Severidade.ALTA,
                )
            )
            pendencias.append(mensagem)


def validar_permissao_usuario(
    contexto: ContextoAntecipacao,
    bloqueios: list[ItemValidacao],
) -> None:
    escopo_necessario = f"{contexto.tipo_processo.value}:{contexto.acao}"

    if escopo_necessario not in contexto.usuario.escopos:
        bloqueios.append(
            ItemValidacao(
                codigo="PERMISSAO_INSUFICIENTE",
                mensagem=f"Usuário não possui o escopo necessário: {escopo_necessario}.",
                campo="usuario.escopos",
                severidade=Severidade.CRITICA,
            )
        )


def validar_evidencias(
    contexto: ContextoAntecipacao,
    bloqueios: list[ItemValidacao],
    alertas: list[ItemValidacao],
    pendencias: list[str],
) -> None:
    evidencias = contexto.dados.get("evidencias", [])

    if contexto.tipo_processo in [TipoProcesso.DEMANDA, TipoProcesso.DOSSIE]:
        if not evidencias:
            bloqueios.append(
                ItemValidacao(
                    codigo="EVIDENCIA_OBRIGATORIA_AUSENTE",
                    mensagem="É obrigatório informar ao menos uma evidência para este tipo de processo.",
                    campo="dados.evidencias",
                    severidade=Severidade.ALTA,
                )
            )
            pendencias.append("Vincular evidência obrigatória.")

    if contexto.tipo_processo == TipoProcesso.SERVICO and not evidencias:
        alertas.append(
            ItemValidacao(
                codigo="SERVICO_SEM_EVIDENCIA",
                mensagem="Serviço sem evidência inicial. O processo pode seguir com ressalva.",
                campo="dados.evidencias",
                severidade=Severidade.MEDIA,
            )
        )


def validar_regras_por_tipo(
    contexto: ContextoAntecipacao,
    bloqueios: list[ItemValidacao],
    alertas: list[ItemValidacao],
    pendencias: list[str],
) -> None:
    if contexto.tipo_processo == TipoProcesso.DEMANDA:
        _validar_demanda(contexto, bloqueios, alertas, pendencias)
    elif contexto.tipo_processo == TipoProcesso.SERVICO:
        _validar_servico(contexto, alertas)
    elif contexto.tipo_processo == TipoProcesso.DOSSIE:
        _validar_dossie(contexto, bloqueios, pendencias)


def _validar_demanda(
    contexto: ContextoAntecipacao,
    bloqueios: list[ItemValidacao],
    alertas: list[ItemValidacao],
    pendencias: list[str],
) -> None:
    dados = contexto.dados

    if not dados.get("criterio_aceite"):
        bloqueios.append(
            ItemValidacao(
                codigo="CRITERIO_ACEITE_AUSENTE",
                mensagem="A demanda precisa ter critério de aceite antes de iniciar.",
                campo="dados.criterio_aceite",
                severidade=Severidade.ALTA,
            )
        )
        pendencias.append("Informar critério de aceite.")

    if not dados.get("valor_negocio"):
        alertas.append(
            ItemValidacao(
                codigo="VALOR_NEGOCIO_AUSENTE",
                mensagem="Valor de negócio não informado. Recomenda-se preencher para priorização.",
                campo="dados.valor_negocio",
                severidade=Severidade.MEDIA,
            )
        )


def _validar_servico(
    contexto: ContextoAntecipacao,
    alertas: list[ItemValidacao],
) -> None:
    if not contexto.dados.get("sla"):
        alertas.append(
            ItemValidacao(
                codigo="SLA_AUSENTE",
                mensagem="SLA não informado para o serviço.",
                campo="dados.sla",
                severidade=Severidade.MEDIA,
            )
        )


def _validar_dossie(
    contexto: ContextoAntecipacao,
    bloqueios: list[ItemValidacao],
    pendencias: list[str],
) -> None:
    documentos = contexto.dados.get("documentos", [])

    if len(documentos) < 2:
        bloqueios.append(
            ItemValidacao(
                codigo="DOSSIE_INCOMPLETO",
                mensagem="Dossiê precisa conter a documentação mínima obrigatória (mínimo 2 documentos).",
                campo="dados.documentos",
                severidade=Severidade.ALTA,
            )
        )
        pendencias.append("Anexar documentação mínima do dossiê.")


def calcular_score_prontidao(
    bloqueios: list[ItemValidacao],
    alertas: list[ItemValidacao],
    pendencias: list[str],
) -> int:
    score = 100
    score -= len(bloqueios) * 25
    score -= len(alertas) * 10
    score -= len(pendencias) * 5
    return max(score, 0)
