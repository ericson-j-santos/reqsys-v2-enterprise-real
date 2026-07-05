from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.orchestrator import AdrCoordinationEvent


@dataclass(frozen=True)
class AdrCoordinatorRule:
    adr_id: str
    coordinator_id: str
    nome: str
    tema: str
    status: str
    nivel_autonomia_maximo: str
    palavras_chave: tuple[str, ...]
    riscos_padrao: tuple[str, ...]
    criterios_aceite: tuple[str, ...]
    automacoes: tuple[str, ...]
    relacionados: tuple[str, ...]


@dataclass(frozen=True)
class AdrDemand:
    titulo: str
    descricao: str = ''
    origem: str = 'chat'
    prioridade_informada: str | None = None
    ambiente: str | None = None
    correlation_id: str | None = None


ADR_COORDINATORS: tuple[AdrCoordinatorRule, ...] = (
    AdrCoordinatorRule(
        adr_id='ADR-001',
        coordinator_id='adr-001-coordinator',
        nome='Coordenador ADR-001 Arquitetura Hexagonal',
        tema='arquitetura_hexagonal',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('hexagonal', 'ports and adapters', 'dominio', 'domínio', 'caso de uso', 'porta', 'adapter', 'acoplamento', 'camada', 'infraestrutura'),
        riscos_padrao=('acoplamento_excessivo', 'dominio_contaminado', 'teste_dependente_de_infra'),
        criterios_aceite=('Domínio sem dependência de infraestrutura', 'Casos de uso isolados com portas explícitas', 'Adaptadores com tratamento de erro', 'Testes unitários no domínio'),
        automacoes=('validar isolamento do dominio', 'sugerir porta/adapter equivalente', 'apontar acoplamento indevido'),
        relacionados=('ADR-010',),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-002',
        coordinator_id='adr-002-coordinator',
        nome='Coordenador ADR-002 LGPD/PII/Mascaramento',
        tema='lgpd_pii_mascaramento',
        status='accepted',
        nivel_autonomia_maximo='N1',
        palavras_chave=('lgpd', 'pii', 'mascarar', 'mascaramento', 'cpf', 'e-mail', 'email', 'senha', 'token', 'connection string', 'dado sensivel', 'dado sensível', 'dado pessoal'),
        riscos_padrao=('pii_exposta', 'segredo_em_log', 'vazamento_de_dado'),
        criterios_aceite=('Função central de mascaramento implementada', 'Testes cobrindo CPF, e-mail, token e connection string', 'CI com validação contra vazamento de segredos', 'Logs estruturados sem dados sensíveis'),
        automacoes=('varrer log em busca de pii', 'sugerir mascaramento', 'bloquear payload sensivel'),
        relacionados=('ADR-003',),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-003',
        coordinator_id='adr-003-coordinator',
        nome='Coordenador ADR-003 Auditoria e Correlação',
        tema='auditoria_correlacao',
        status='accepted',
        nivel_autonomia_maximo='N1',
        palavras_chave=('correlation_id', 'correlation id', 'auditoria', 'rastreabilidade', 'rastreio', 'evento auditavel', 'evento auditável', 'log estruturado'),
        riscos_padrao=('correlation_id_ausente', 'evento_critico_sem_auditoria', 'log_sem_rastreio'),
        criterios_aceite=('correlation_id criado quando ausente', 'correlation_id propagado entre todas as camadas', 'Auditoria persistida para eventos críticos'),
        automacoes=('gerar correlation_id', 'validar propagacao ponta a ponta', 'registrar evento auditavel'),
        relacionados=('ADR-002', 'ADR-007'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-004',
        coordinator_id='adr-004-coordinator',
        nome='Coordenador ADR-004 Autenticação/JWT/RBAC',
        tema='autenticacao_jwt_rbac',
        status='accepted',
        nivel_autonomia_maximo='N1',
        palavras_chave=('jwt', 'rbac', 'autenticacao', 'autenticação', 'autorizacao', 'autorização', 'cors', 'issuer', 'audience', 'papel', 'permissao', 'permissão', 'admin publico'),
        riscos_padrao=('auth_desligada', 'cors_aberto', 'jwt_sem_validacao', 'endpoint_admin_publico'),
        criterios_aceite=('Autenticação obrigatória em produção', 'JWT validando issuer, audience, expiração e assinatura', 'RBAC aplicado em rotas críticas', 'CORS restrito por ambiente'),
        automacoes=('validar configuracao jwt', 'checar rbac de rota critica', 'bloquear cors aberto'),
        relacionados=('ADR-005', 'ADR-003'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-005',
        coordinator_id='adr-005-coordinator',
        nome='Coordenador ADR-005 Segregação de Ambientes',
        tema='segregacao_ambientes',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('ambiente', 'producao', 'produção', 'homologacao', 'homologação', 'desenvolvimento', 'gate', 'deploy', 'debug', 'tls verify desativado', 'variavel de ambiente', 'variável de ambiente'),
        riscos_padrao=('deploy_sem_gate', 'debug_ativo_producao', 'secret_hardcoded'),
        criterios_aceite=('Validador de ambiente implementado no boot', 'Testes para cada bloqueio produtivo', 'CI executa validação de ambiente'),
        automacoes=('rodar validador de ambiente', 'checar variaveis obrigatorias', 'bloquear promocao insegura'),
        relacionados=('ADR-004', 'ADR-006'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-006',
        coordinator_id='adr-006-coordinator',
        nome='Coordenador ADR-006 CI/CD e Quality Gates',
        tema='cicd_quality_gates',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('ci', 'cd', 'pipeline', 'pull request', 'pr ', 'quality gate', 'draft', 'merge', 'branch', 'changelog', 'lint', 'cobertura'),
        riscos_padrao=('merge_sem_gate', 'pr_sem_evidencia', 'ci_instavel'),
        criterios_aceite=('PR vinculado a issue, demanda ou decisão', 'CI verde antes do merge', 'Evidências registradas', 'Documentação e changelog atualizados'),
        automacoes=('checar gates minimos do pr', 'sugerir manter pr em draft', 'cobrar evidencia de teste'),
        relacionados=('ADR-005', 'ADR-012'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-007',
        coordinator_id='adr-007-coordinator',
        nome='Coordenador ADR-007 Observabilidade',
        tema='observabilidade',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('observabilidade', 'health', 'readiness', 'liveness', 'metrica', 'métrica', 'telemetria', 'painel operacional', 'severidade', 'runtime health'),
        riscos_padrao=('health_sem_evidencia', 'estado_cinza_nao_investigado', 'metrica_ausente'),
        criterios_aceite=('Endpoint /health implementado', 'Endpoint /readiness implementado', 'Painel operacional exibe status por domínio'),
        automacoes=('validar health/readiness', 'classificar severidade', 'atualizar painel operacional'),
        relacionados=('ADR-003', 'ADR-011'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-008',
        coordinator_id='adr-008-coordinator',
        nome='Coordenador ADR-008 IA Governada/RAG',
        tema='ia_governada_rag',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('ia', 'rag', 'alucinacao', 'alucinação', 'prompt', 'embedding', 'explainability', 'fonte da resposta', 'confianca', 'confiança', 'sql gerado por ia'),
        riscos_padrao=('resposta_sem_fonte', 'acao_ia_nao_auditada', 'sql_ia_nao_validado'),
        criterios_aceite=('Respostas com fonte retornam referência', 'Respostas sem evidência não inventam informação', 'SQL gerado por IA deve ser validado antes de executar'),
        automacoes=('validar presenca de fonte', 'classificar confianca da resposta', 'bloquear sql nao validado'),
        relacionados=('ADR-002', 'ADR-003', 'ADR-011'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-009',
        coordinator_id='adr-009-coordinator',
        nome='Coordenador ADR-009 Frontend Schema-Driven',
        tema='frontend_schema_driven',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('frontend', 'ui', 'ux', 'drill-down', 'drilldown', 'card clicavel', 'card clicável', 'dashboard', 'responsivo', 'responsividade', 'schema-driven'),
        riscos_padrao=('drilldown_sem_fonte', 'card_sem_filtro_server_side', 'cor_fora_do_padrao'),
        criterios_aceite=('Layout responsivo validado', 'Indicadores críticos com drill-down', 'Cores seguem padrão único', 'Fonte dos dados exibida'),
        automacoes=('validar drill-down do indicador', 'checar filtro server-side', 'validar padrao de cores'),
        relacionados=('ADR-012',),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-010',
        coordinator_id='adr-010-coordinator',
        nome='Coordenador ADR-010 Integrações e Adapters',
        tema='integracoes_adapters',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('integracao', 'integração', 'adapter', 'timeout', 'retry', 'backoff', 'circuit breaker', 'idempotencia', 'idempotência', 'webhook', 'conector'),
        riscos_padrao=('chamada_sem_timeout', 'retry_infinito', 'escrita_sem_idempotencia'),
        criterios_aceite=('Adapter isolado com interface/porta definida', 'Timeout configurado', 'Retry controlado com limite', 'Testes de sucesso, falha e timeout'),
        automacoes=('validar timeout/retry/circuit breaker', 'checar idempotencia de escrita', 'revisar logs sanitizados da integracao'),
        relacionados=('ADR-001', 'ADR-003'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-011',
        coordinator_id='adr-011-coordinator',
        nome='Coordenador ADR-011 Operação Autônoma',
        tema='operacao_autonoma',
        status='proposed',
        nivel_autonomia_maximo='N4',
        palavras_chave=('autonomia', 'autonomo', 'autônomo', 'remediacao', 'remediação', 'dry-run', 'dry run', 'rollback', 'guard rail', 'guardrail', 'acao automatica', 'ação automática'),
        riscos_padrao=('acao_sem_autorizacao', 'loop_de_remediacao', 'acao_sem_evidencia'),
        criterios_aceite=('Classificador de risco implementado', 'Executor governado com dry-run', 'Auditoria de cada ação', 'Limite de tentativas'),
        automacoes=('classificar nivel de autonomia', 'exigir dry-run antes de execucao', 'bloquear acao repetida sem evidencia'),
        relacionados=('ADR-007', 'ADR-008', 'ADR-003'),
    ),
    AdrCoordinatorRule(
        adr_id='ADR-012',
        coordinator_id='adr-012-coordinator',
        nome='Coordenador ADR-012 Documentação Viva',
        tema='documentacao_viva',
        status='accepted',
        nivel_autonomia_maximo='N2',
        palavras_chave=('documentacao', 'documentação', 'changelog', 'readme', 'diagrama', 'mermaid', 'relatorio html', 'relatório html', 'estado atual', 'estado alvo', 'arquitetura viva'),
        riscos_padrao=('documentacao_desatualizada', 'evidencia_declarada_nao_real', 'estado_nao_diferenciado'),
        criterios_aceite=('ADR criado ou atualizado quando houver decisão', 'CHANGELOG atualizado', 'Estado atual diferenciado do estado alvo', 'Evidência real registrada'),
        automacoes=('gerar changelog', 'atualizar readme', 'diferenciar estado atual vs alvo vs gaps'),
        relacionados=('ADR-006', 'ADR-009'),
    ),
)

GENERAL_COORDINATOR_ID = 'adr-geral-coordinator'

DEFAULT_ADR_COORDINATOR = AdrCoordinatorRule(
    adr_id='ADR-000',
    coordinator_id='adr-intake-coordinator',
    nome='Coordenador ADR Intake Central',
    tema='intake',
    status='accepted',
    nivel_autonomia_maximo='N0',
    palavras_chave=(),
    riscos_padrao=('tema_ambiguo', 'escopo_insuficiente'),
    criterios_aceite=('Demanda associada a um ADR apos refinamento',),
    automacoes=('refinar escopo', 'classificar ADR posteriormente'),
    relacionados=(),
)

_VIOLATION_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ('cors_wildcard', re.compile(r'cors[^\n]{0,25}\*'), 'ADR-004'),
    ('auth_desligada', re.compile(r'auth[_ ]?enabled\s*[:=]\s*false', re.I), 'ADR-004'),
    ('jwt_sem_issuer', re.compile(r'jwt[_ ]?issuer\s*(ausente|not set|none|vazio)', re.I), 'ADR-004'),
    ('verify_false', re.compile(r'verify\s*=\s*false', re.I), 'ADR-010'),
    ('debug_ativo', re.compile(r'debug\s*[:=]\s*true', re.I), 'ADR-005'),
    ('secret_hardcoded', re.compile(r'(api[_-]?key|secret|senha|password)\s*[:=]\s*[\'"][^\'"]+[\'"]', re.I), 'ADR-002'),
    ('retry_infinito', re.compile(r'retry\s*(infinito|sem limite|unlimited)', re.I), 'ADR-010'),
)

_STATUS_RISCO = {'baixo': 0, 'medio': 1, 'alto': 2, 'critico': 3}


def _normalizar_texto(valor: str) -> str:
    return valor.lower().strip()


def _score_rule(texto: str, rule: AdrCoordinatorRule) -> int:
    return sum(1 for palavra in rule.palavras_chave if palavra in texto)


def _detectar_violacoes(texto_original: str) -> list[dict]:
    return [
        {'violacao': nome, 'adr_relacionado': adr_id}
        for nome, pattern, adr_id in _VIOLATION_PATTERNS
        if pattern.search(texto_original)
    ]


def _prioridade(score: int, demanda: AdrDemand) -> str:
    if demanda.prioridade_informada:
        return demanda.prioridade_informada
    if score >= 3:
        return 'alta'
    if score == 2:
        return 'media'
    return 'normal'


def _confianca(score: int) -> float:
    if score <= 0:
        return 0.45
    return min(0.96, 0.58 + (score * 0.1))


def _nivel_risco(score: int, violacoes: list[dict], rule: AdrCoordinatorRule) -> str:
    if violacoes:
        return 'critico'
    if rule.status == 'proposed':
        return 'alto'
    if score >= 3:
        return 'medio'
    return 'baixo'


def _requer_aprovacao_humana(rule: AdrCoordinatorRule, violacoes: list[dict]) -> bool:
    if violacoes:
        return True
    if rule.status == 'proposed':
        return True
    return rule.adr_id in ('ADR-004', 'ADR-005', 'ADR-011')


def _serializar_rule(rule: AdrCoordinatorRule, score: int) -> dict:
    return {
        'adr_id': rule.adr_id,
        'coordinator_id': rule.coordinator_id,
        'nome': rule.nome,
        'tema': rule.tema,
        'status': rule.status,
        'score': score,
        'nivel_autonomia_maximo': rule.nivel_autonomia_maximo,
        'relacionados': list(rule.relacionados),
    }


def listar_coordenadores_adr() -> list[dict]:
    return [
        {
            'adr_id': rule.adr_id,
            'coordinator_id': rule.coordinator_id,
            'nome': rule.nome,
            'tema': rule.tema,
            'status': rule.status,
            'nivel_autonomia_maximo': rule.nivel_autonomia_maximo,
            'palavras_chave': list(rule.palavras_chave),
            'riscos_padrao': list(rule.riscos_padrao),
            'criterios_aceite': list(rule.criterios_aceite),
            'automacoes': list(rule.automacoes),
            'relacionados': list(rule.relacionados),
        }
        for rule in ADR_COORDINATORS
    ]


def _proximo_passo(rule: AdrCoordinatorRule, score: int, violacoes: list[dict]) -> str:
    if violacoes:
        nomes = ', '.join(v['violacao'] for v in violacoes)
        return f'Bloquear execução e corrigir violação(oes) de gate antes de prosseguir: {nomes}.'
    if rule == DEFAULT_ADR_COORDINATOR or score == 0:
        return 'Refinar demanda no intake central de ADRs antes de associar a um ADR especifico.'
    return f'Encaminhar para {rule.nome} e executar automação assistida: {rule.automacoes[0]}.'


def coordenar_geral(demanda: AdrDemand) -> dict:
    texto_original = f'{demanda.titulo} {demanda.descricao}'
    texto = _normalizar_texto(texto_original)

    ranking = sorted(
        ((_score_rule(texto, rule), rule) for rule in ADR_COORDINATORS),
        key=lambda item: (item[0], item[1].adr_id),
        reverse=True,
    )
    score_primario, rule_primaria = ranking[0]
    if score_primario == 0:
        rule_primaria = DEFAULT_ADR_COORDINATOR

    adrs_relacionados = [
        _serializar_rule(rule, score) for score, rule in ranking if score > 0 and rule.adr_id != rule_primaria.adr_id
    ]

    violacoes = _detectar_violacoes(texto_original)
    prioridade = _prioridade(score_primario, demanda)
    confianca = _confianca(score_primario)
    nivel_risco = _nivel_risco(score_primario, violacoes, rule_primaria)
    requer_aprovacao = _requer_aprovacao_humana(rule_primaria, violacoes)
    agora = datetime.now(UTC).isoformat()

    labels = [f'adr:{rule_primaria.adr_id.lower()}', f'tema:{rule_primaria.tema}']
    if demanda.ambiente:
        labels.append(f'ambiente:{demanda.ambiente}')
    if violacoes:
        labels.append('violacao-gate')
    if prioridade in ('alta', 'critica', 'crítica'):
        labels.append('prioridade-alta')

    return {
        'schema_version': '1.0.0',
        'classified_at': agora,
        'correlation_id': demanda.correlation_id,
        'origem': demanda.origem,
        'coordenacao_geral': {
            'coordinator_id': GENERAL_COORDINATOR_ID,
            'nome': 'Coordenação Geral de ADRs',
        },
        'adr_primario': _serializar_rule(rule_primaria, score_primario),
        'adrs_relacionados': adrs_relacionados,
        'multi_adr': len(adrs_relacionados) > 0,
        'prioridade_sugerida': prioridade,
        'ambiente': demanda.ambiente or 'nao_informado',
        'confianca': round(confianca, 2),
        'nivel_risco': nivel_risco,
        'violacoes_detectadas': violacoes,
        'labels': labels,
        'automacoes_recomendadas': list(rule_primaria.automacoes),
        'criterios_aceite_pendentes': list(rule_primaria.criterios_aceite),
        'governanca': {
            'modo_execucao': 'assistido',
            'requer_aprovacao_humana': requer_aprovacao,
            'gera_evidencia': True,
            'permite_acao_destrutiva': False,
            'nivel_autonomia_sugerido': rule_primaria.nivel_autonomia_maximo if not violacoes else 'N0',
        },
        'proximo_passo': _proximo_passo(rule_primaria, score_primario, violacoes),
    }


def coordenar_lote(demandas: Iterable[AdrDemand]) -> dict:
    rotas = [coordenar_geral(demanda) for demanda in demandas]
    por_adr: dict[str, int] = {}
    for rota in rotas:
        adr_id = rota['adr_primario']['adr_id']
        por_adr[adr_id] = por_adr.get(adr_id, 0) + 1
    return {
        'schema_version': '1.0.0',
        'total': len(rotas),
        'por_adr': por_adr,
        'rotas': rotas,
    }


def _payload_hash(demanda: AdrDemand) -> str:
    payload = {
        'titulo': demanda.titulo,
        'descricao': demanda.descricao,
        'origem': demanda.origem,
        'prioridade_informada': demanda.prioridade_informada,
        'ambiente': demanda.ambiente,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def registrar_evento_coordenacao(db: Session, demanda: AdrDemand, rota: dict) -> AdrCoordinationEvent:
    adrs_relacionados = [item['adr_id'] for item in rota['adrs_relacionados']]
    violacoes = [v['violacao'] for v in rota['violacoes_detectadas']]
    evento = AdrCoordinationEvent(
        correlation_id=demanda.correlation_id,
        adr_primario=rota['adr_primario']['adr_id'],
        coordinator_id=rota['adr_primario']['coordinator_id'],
        adrs_relacionados=json.dumps(adrs_relacionados, ensure_ascii=False),
        prioridade=rota['prioridade_sugerida'],
        score=rota['adr_primario']['score'],
        confianca=rota['confianca'],
        nivel_risco=rota['nivel_risco'],
        violacoes=json.dumps(violacoes, ensure_ascii=False),
        origem=rota['origem'],
        ambiente=rota['ambiente'],
        payload_hash=_payload_hash(demanda),
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


def coordenar_e_persistir_demanda(db: Session, demanda: AdrDemand) -> dict:
    rota = coordenar_geral(demanda)
    evento = registrar_evento_coordenacao(db, demanda, rota)
    rota['coordination_event_id'] = evento.id
    return rota


def coordenar_e_persistir_lote(db: Session, demandas: Iterable[AdrDemand]) -> dict:
    demandas_materializadas = list(demandas)
    rotas = [coordenar_e_persistir_demanda(db, demanda) for demanda in demandas_materializadas]
    por_adr: dict[str, int] = {}
    for rota in rotas:
        adr_id = rota['adr_primario']['adr_id']
        por_adr[adr_id] = por_adr.get(adr_id, 0) + 1
    return {
        'schema_version': '1.0.0',
        'total': len(rotas),
        'por_adr': por_adr,
        'rotas': rotas,
    }


def analytics_summary(db: Session) -> dict:
    total = db.query(func.count(AdrCoordinationEvent.id)).scalar() or 0
    avg_score = db.query(func.avg(AdrCoordinationEvent.score)).scalar() or 0
    avg_confianca = db.query(func.avg(AdrCoordinationEvent.confianca)).scalar() or 0
    ultimo = db.query(AdrCoordinationEvent).order_by(desc(AdrCoordinationEvent.created_at), desc(AdrCoordinationEvent.id)).first()
    return {
        'schema_version': '1.0.0',
        'total_eventos': total,
        'score_medio': round(float(avg_score), 2),
        'confianca_media': round(float(avg_confianca), 2),
        'ultimo_evento_em': ultimo.created_at.isoformat() if ultimo and ultimo.created_at else None,
    }


def _counter(db: Session, column) -> list[dict]:
    rows = db.query(column, func.count(AdrCoordinationEvent.id)).group_by(column).order_by(desc(func.count(AdrCoordinationEvent.id)), column).all()
    return [{'valor': value, 'total': total} for value, total in rows]


def analytics_adrs(db: Session) -> dict:
    return {'schema_version': '1.0.0', 'adrs': _counter(db, AdrCoordinationEvent.adr_primario)}


def analytics_coordinators(db: Session) -> dict:
    return {'schema_version': '1.0.0', 'coordinators': _counter(db, AdrCoordinationEvent.coordinator_id)}


def analytics_risk(db: Session) -> dict:
    critico = db.query(func.count(AdrCoordinationEvent.id)).filter(AdrCoordinationEvent.nivel_risco == 'critico').scalar() or 0
    alto = db.query(func.count(AdrCoordinationEvent.id)).filter(AdrCoordinationEvent.nivel_risco == 'alto').scalar() or 0
    baixa_confianca = db.query(func.count(AdrCoordinationEvent.id)).filter(AdrCoordinationEvent.confianca < 0.6).scalar() or 0
    total_violacoes = db.query(func.count(AdrCoordinationEvent.id)).filter(AdrCoordinationEvent.violacoes != '[]').scalar() or 0
    return {
        'schema_version': '1.0.0',
        'risk': {
            'nivel_critico': critico,
            'nivel_alto': alto,
            'baixa_confianca': baixa_confianca,
            'com_violacao_de_gate': total_violacoes,
        },
    }
