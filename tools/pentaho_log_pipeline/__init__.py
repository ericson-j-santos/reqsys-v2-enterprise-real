"""Pipeline governado de logs Pentaho.

O pacote mantém Pentaho e cron como produtores e usa SQL Server como plano de
controle para idempotência, leases, retentativas, quarentena e retenção.
"""

from .pipeline import build_idempotency_key, sha256_file

__all__ = ["build_idempotency_key", "sha256_file"]
