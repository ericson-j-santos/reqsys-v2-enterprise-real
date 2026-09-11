"""
Métricas Prometheus para OCR v2

Expõe:
- ocr_readiness_status: Status de readiness (0=not ready, 1=ready)
- ocr_jobs_processed_total: Total de jobs processados
- ocr_jobs_errors_total: Total de erros em processamento
- ocr_encryption_key_rotation_days: Dias desde última rotação
"""

import os

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
)

# ============================================================================
# Gauges (métricas que podem aumentar ou diminuir)
# ============================================================================

ocr_readiness_status = Gauge(
    'ocr_readiness_status',
    'OCR readiness check (1=ready, 0=not ready)',
    labelnames=['environment', 'component']
)

ocr_jobs_pending_count = Gauge(
    'ocr_jobs_pending_count',
    'Número de jobs OCR pendentes para revisão humana',
    labelnames=['environment', 'tipo_documento']
)

ocr_encryption_key_age_days = Gauge(
    'ocr_encryption_key_age_days',
    'Dias desde geração da chave de criptografia',
    labelnames=['environment', 'key_version']
)

ocr_input_root_size_bytes = Gauge(
    'ocr_input_root_size_bytes',
    'Tamanho total do diretório OCR_INPUT_ROOT em bytes',
    labelnames=['environment']
)

# ============================================================================
# Counters (métricas que apenas aumentam)
# ============================================================================

ocr_jobs_processed_total = Counter(
    'ocr_jobs_processed_total',
    'Total de jobs OCR processados',
    labelnames=['environment', 'status', 'tipo_documento']
)

ocr_jobs_auto_approved_total = Counter(
    'ocr_jobs_auto_approved_total',
    'Jobs aprovados automaticamente (status=AUTO)',
    labelnames=['environment', 'tipo_documento']
)

ocr_jobs_manual_review_total = Counter(
    'ocr_jobs_manual_review_total',
    'Jobs enviados para revisão manual',
    labelnames=['environment', 'motivo']
)

ocr_errors_total = Counter(
    'ocr_errors_total',
    'Total de erros no processamento OCR',
    labelnames=['environment', 'tipo_erro']
)

ocr_encryption_errors_total = Counter(
    'ocr_encryption_errors_total',
    'Erros de criptografia/descriptografia',
    labelnames=['environment', 'operacao']
)

# ============================================================================
# Histograms (distribuição de valores)
# ============================================================================

ocr_processing_duration_seconds = Histogram(
    'ocr_processing_duration_seconds',
    'Tempo de processamento OCR em segundos',
    labelnames=['environment', 'tipo_documento'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

ocr_encryption_duration_seconds = Histogram(
    'ocr_encryption_duration_seconds',
    'Tempo de criptografia de payload em segundos',
    labelnames=['environment', 'tamanho_kb'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1)
)

# ============================================================================
# Info (metadata)
# ============================================================================

ocr_system_info = Info(
    'ocr_system_info',
    'Informações do sistema OCR',
    labelnames=['version', 'encryption_algo', 'environment']
)

# ============================================================================
# Funções de atualização
# ============================================================================

def update_readiness_metrics(ready: bool, environment: str = "development"):
    """Atualizar métricas de readiness"""
    status = 1 if ready else 0

    ocr_readiness_status.labels(
        environment=environment,
        component="encryption"
    ).set(status)

    ocr_readiness_status.labels(
        environment=environment,
        component="input_root"
    ).set(status)


def record_job_processed(
    environment: str,
    status: str,
    tipo_documento: str,
    duration_seconds: float
):
    """Registrar job processado"""
    ocr_jobs_processed_total.labels(
        environment=environment,
        status=status,
        tipo_documento=tipo_documento
    ).inc()

    ocr_processing_duration_seconds.labels(
        environment=environment,
        tipo_documento=tipo_documento
    ).observe(duration_seconds)

    if status == "AUTO":
        ocr_jobs_auto_approved_total.labels(
            environment=environment,
            tipo_documento=tipo_documento
        ).inc()


def record_manual_review_job(
    environment: str,
    motivo: str
):
    """Registrar job enviado para revisão manual"""
    ocr_jobs_manual_review_total.labels(
        environment=environment,
        motivo=motivo
    ).inc()


def record_encryption_operation(
    environment: str,
    operacao: str,
    duration_seconds: float,
    tamanho_kb: float = 1.0
):
    """Registrar operação de criptografia"""
    ocr_encryption_duration_seconds.labels(
        environment=environment,
        tamanho_kb=str(int(tamanho_kb))
    ).observe(duration_seconds)


def record_error(
    environment: str,
    tipo_erro: str
):
    """Registrar erro de processamento"""
    ocr_errors_total.labels(
        environment=environment,
        tipo_erro=tipo_erro
    ).inc()


def record_encryption_error(
    environment: str,
    operacao: str
):
    """Registrar erro de criptografia"""
    ocr_encryption_errors_total.labels(
        environment=environment,
        operacao=operacao
    ).inc()


def update_pending_count(
    environment: str,
    tipo_documento: str,
    count: int
):
    """Atualizar contagem de jobs pendentes"""
    ocr_jobs_pending_count.labels(
        environment=environment,
        tipo_documento=tipo_documento
    ).set(count)


def update_key_age(
    environment: str,
    key_version: str,
    days: int
):
    """Atualizar idade da chave de criptografia"""
    ocr_encryption_key_age_days.labels(
        environment=environment,
        key_version=key_version
    ).set(days)


def initialize_system_info():
    """Inicializar informações do sistema"""
    ocr_system_info.labels(
        version="2.0",
        encryption_algo="AES-256-GCM",
        environment=os.getenv("APP_ENV", "development")
    ).info({})
