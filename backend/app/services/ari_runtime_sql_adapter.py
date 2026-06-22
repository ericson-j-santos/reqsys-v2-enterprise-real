from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AriSqlValidationItem:
    regra: str
    estado: str
    score: int
    evidencia: str
    gap: str


class AriRuntimeSqlAdapter:
    def validate(self, sql: str, null_critical: int = 0, source_name: str = 'runtime-sql') -> dict:
        normalized = self._normalize(sql)
        items = [
            self._validate_count(normalized),
            self._validate_join(normalized),
            self._validate_filters(normalized),
            self._validate_group_by(normalized),
            self._validate_nulls(null_critical),
        ]
        score = round(sum(item.score for item in items) / len(items)) if items else 0
        blockers = [item for item in items if item.estado in {'FAIL', 'BLOCK'}]
        return {
            'source_name': source_name,
            'adapter': 'AriRuntimeSqlAdapter',
            'runtime_sql_score': score,
            'runtime_sql_ready': not blockers,
            'validations': [item.__dict__ for item in items],
            'blockers': [item.__dict__ for item in blockers],
        }

    def _normalize(self, sql: str) -> str:
        return ' '.join((sql or '').upper().split())

    def _validate_count(self, sql: str) -> AriSqlValidationItem:
        has_count = 'COUNT(' in sql or 'COUNT (' in sql
        return AriSqlValidationItem(
            regra='COUNT_VALIDATION',
            estado='VALIDADO' if has_count else 'PARCIAL',
            score=96 if has_count else 82,
            evidencia='Consulta possui checkpoint de volume.' if has_count else 'Consulta sem COUNT explicito no adapter.',
            gap='Adicionar checkpoint COUNT antes/depois.' if not has_count else 'Persistir baseline real.',
        )

    def _validate_join(self, sql: str) -> AriSqlValidationItem:
        joins = sql.count(' JOIN ')
        if joins >= 8:
            return AriSqlValidationItem('JOIN_CARDINALITY', 'FAIL', 45, 'Quantidade elevada de JOINs detectada.', 'Revisar cardinalidade e chaves.')
        if joins == 0:
            return AriSqlValidationItem('JOIN_CARDINALITY', 'PARCIAL', 85, 'Consulta sem JOIN para validar cardinalidade.', 'Confirmar se a consulta deveria cruzar fontes.')
        return AriSqlValidationItem('JOIN_CARDINALITY', 'VALIDADO', 94, 'JOINs detectados dentro do limite inicial.', 'Persistir baseline por dominio.')

    def _validate_filters(self, sql: str) -> AriSqlValidationItem:
        if ' WHERE ' not in f' {sql} ':
            return AriSqlValidationItem('FILTER_ISOLATION', 'PARCIAL', 80, 'Consulta sem WHERE explicito.', 'Adicionar filtros auditaveis ou justificar full scan.')
        return AriSqlValidationItem('FILTER_ISOLATION', 'VALIDADO', 94, 'Filtro identificado para isolamento operacional.', 'Medir impacto percentual por filtro.')

    def _validate_group_by(self, sql: str) -> AriSqlValidationItem:
        if 'GROUP BY' not in sql:
            return AriSqlValidationItem('GROUP_BY_GRANULARITY', 'PARCIAL', 84, 'Consulta sem GROUP BY explicito.', 'Confirmar granularidade esperada.')
        return AriSqlValidationItem('GROUP_BY_GRANULARITY', 'VALIDADO', 96, 'Granularidade explicita identificada.', 'Exibir dimensoes no drill-down.')

    def _validate_nulls(self, null_critical: int) -> AriSqlValidationItem:
        if null_critical > 0:
            return AriSqlValidationItem('NULL_CRITICAL', 'FAIL', 35, 'Null critico informado na validacao.', 'Corrigir origem, carga ou relacionamento.')
        return AriSqlValidationItem('NULL_CRITICAL', 'VALIDADO', 97, 'Nenhum null critico informado.', 'Conectar catalogo de obrigatoriedade.')
