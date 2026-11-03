"""Coleta limitada, auditável e fail-closed dos runs do Dashboard Teams."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from typing import Callable


class WorkflowRunQueryError(RuntimeError):
    """A janela de observação não pôde ser consultada integralmente."""


def collect_recent_workflow_runs(
    repository: str,
    filename: str,
    cutoff: datetime,
    *,
    runner: Callable = subprocess.run,
    sleeper: Callable = time.sleep,
    max_pages: int = 200,
    max_elapsed_seconds: float = 480.0,
    clock: Callable[[], float] = time.monotonic,
) -> list[dict]:
    """Consulta páginas recentes até a primeira data anterior ao corte.

    Falha explicitamente diante de respostas inválidas, erros permanentes,
    ordenação inesperada e limite de páginas: nunca calcula SLO parcial.
    """
    if cutoff.tzinfo is None or max_pages < 1 or max_elapsed_seconds <= 0:
        raise ValueError("cutoff deve ter fuso e limites devem ser positivos")

    runs: list[dict] = []
    started_at = clock()
    previous_created: datetime | None = None
    for page in range(1, max_pages + 1):
        if clock() - started_at >= max_elapsed_seconds:
            raise WorkflowRunQueryError(f"Prazo de coleta excedido: {filename}, page={page}")
        command = [
            "gh", "api", "--jq", ".workflow_runs",
            f"repos/{repository}/actions/workflows/{filename}/runs?per_page=100&page={page}",
        ]
        for attempt in range(3):
            if clock() - started_at >= max_elapsed_seconds:
                raise WorkflowRunQueryError(f"Prazo de coleta excedido: {filename}, page={page}")
            try:
                result = runner(command, text=True, capture_output=True, check=False, timeout=30)
            except subprocess.TimeoutExpired as exc:
                if attempt == 2:
                    raise WorkflowRunQueryError(f"API timeout: {filename}, page={page}") from exc
                sleeper(2 ** attempt)
                continue
            if result.returncode == 0:
                break
            details = str(result.stderr or "")
            retryable = any(code in details for code in ("HTTP 429", "HTTP 502", "HTTP 503", "HTTP 504"))
            if not retryable or attempt == 2:
                raise WorkflowRunQueryError(f"API falhou: {filename}, page={page}, retryable={retryable}")
            sleeper(2 ** attempt)

        try:
            items = json.loads(result.stdout)
        except (TypeError, ValueError) as exc:
            raise WorkflowRunQueryError(f"JSON inválido: {filename}, page={page}") from exc
        if not isinstance(items, list) or len(items) > 100:
            raise WorkflowRunQueryError(f"Página fora do contrato: {filename}, page={page}")
        if not items:
            return runs

        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("created_at"), str):
                raise WorkflowRunQueryError(f"Run sem timestamp: {filename}, page={page}")
            try:
                created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            except ValueError as exc:
                raise WorkflowRunQueryError(f"Timestamp inválido: {filename}, page={page}") from exc
            if created.tzinfo is None:
                raise WorkflowRunQueryError(f"Timestamp sem fuso: {filename}, page={page}")
            if previous_created is not None and created > previous_created:
                raise WorkflowRunQueryError(f"Runs fora de ordem: {filename}, page={page}")
            previous_created = created
            if created < cutoff:
                return runs
            if item.get("status") == "completed":
                runs.append(item)

        if len(items) < 100:
            return runs

    raise WorkflowRunQueryError(f"Limite de páginas excedido: {filename}, max_pages={max_pages}")
