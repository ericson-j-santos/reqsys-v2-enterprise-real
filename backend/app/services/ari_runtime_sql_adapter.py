from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AriSqlValidationItem:
    regra: str
    estado: str
    score: int
    evidencia: str
    gap: str


class AriRuntimeSqlAdapter:
    """Validação estática; nunca abre conexão nem executa SQL."""

    _destructive = re.compile(
        r'\b(delete|update|insert|drop|truncate|alter|create|grant|revoke)\b',
        flags=re.IGNORECASE,
    )

    def validate(self, sql: str, null_critical: int = 0, source_name: str = 'runtime-sql') -> dict:
        normalized = self._normalize(sql)
        items = [
            self._validate_destructive(normalized),
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
            'execution_mode': 'static_only',
            'production_evidence': False,
            'query_sha256': hashlib.sha256(normalized.encode('utf-8')).hexdigest(),
            'runtime_sql_score': score,
            'runtime_sql_ready': not blockers,
            'validations': [asdict(item) for item in items],
            'blockers': [asdict(item) for item in blockers],
        }

    def _normalize(self, sql: str) -> str:
        without_line_comments = re.sub(r'--.*$', '', str(sql or ''), flags=re.MULTILINE)
        without_block_comments = re.sub(r'/\*[\s\S]*?\*/', '', without_line_comments)
        return ' '.join(without_block_comments.upper().split())

    def _validate_destructive(self, sql: str) -> AriSqlValidationItem:
        match = self._destructive.search(sql)
        if match:
            return AriSqlValidationItem(
                'DESTRUCTIVE_SQL',
                'BLOCK',
                0,
                f'Comando potencialmente destrutivo detectado: {match.group(1).upper()}.',
                'Usar somente análise estática e revisão humana.',
            )
        return AriSqlValidationItem('DESTRUCTIVE_SQL', 'VALIDADO', 100, 'Nenhum comando mutável detectado.', 'Manter análise sem execução.')

    def _validate_count(self, sql: str) -> AriSqlValidationItem:
        has_count = 'COUNT(' in sql or 'COUNT (' in sql
        return AriSqlValidationItem(
            'COUNT_VALIDATION',
            'VALIDADO' if has_count else 'PARCIAL',
            96 if has_count else 82,
            'Checkpoint COUNT identificado.' if has_count else 'Consulta sem COUNT explícito.',
            'Adicionar checkpoint COUNT quando o caso exigir reconciliação de volume.',
        )

    def _validate_join(self, sql: str) -> AriSqlValidationItem:
        joins = sql.count(' JOIN ')
        if joins >= 8:
            return AriSqlValidationItem('JOIN_CARDINALITY', 'FAIL', 45, 'Quantidade elevada de JOINs detectada.', 'Revisar cardinalidade e chaves.')
        if joins == 0:
            return AriSqlValidationItem('JOIN_CARDINALITY', 'PARCIAL', 85, 'Consulta sem JOIN.', 'Confirmar se cruzamento de fontes é esperado.')
        return AriSqlValidationItem('JOIN_CARDINALITY', 'VALIDADO', 94, 'JOINs abaixo do limite estático.', 'Medir cardinalidade real em ambiente controlado.')

    def _validate_filters(self, sql: str) -> AriSqlValidationItem:
        if ' WHERE ' not in f' {sql} ':
            return AriSqlValidationItem('FILTER_ISOLATION', 'PARCIAL', 80, 'Consulta sem WHERE.', 'Justificar full scan ou adicionar filtros.')
        return AriSqlValidationItem('FILTER_ISOLATION', 'VALIDADO', 94, 'Filtro identificado.', 'Medir impacto real por filtro.')

    def _validate_group_by(self, sql: str) -> AriSqlValidationItem:
        if 'GROUP BY' not in sql:
            return AriSqlValidationItem('GROUP_BY_GRANULARITY', 'PARCIAL', 84, 'Consulta sem GROUP BY.', 'Confirmar granularidade esperada.')
        return AriSqlValidationItem('GROUP_BY_GRANULARITY', 'VALIDADO', 96, 'Granularidade explícita identificada.', 'Validar dimensões contra a fonte real.')

    def _validate_nulls(self, null_critical: int) -> AriSqlValidationItem:
        if null_critical > 0:
            return AriSqlValidationItem('NULL_CRITICAL', 'FAIL', 35, 'Null crítico informado.', 'Corrigir origem, carga ou relacionamento.')
        return AriSqlValidationItem('NULL_CRITICAL', 'VALIDADO', 97, 'Nenhum null crítico informado ao adapter.', 'Conectar catálogo real de obrigatoriedade.')
