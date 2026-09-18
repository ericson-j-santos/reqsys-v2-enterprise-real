from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _conteudo_python_backend() -> str:
    arquivos = sorted((ROOT / "backend" / "app").rglob("*.py"))
    return "\n".join(arquivo.read_text(encoding="utf-8", errors="ignore") for arquivo in arquivos)


def test_backend_possui_timeout_explicito_em_integracoes() -> None:
    conteudo = _conteudo_python_backend().lower()
    assert "timeout" in conteudo, "Integrações devem definir timeout explícito."


def test_backend_possui_estrategia_de_retry_ou_backoff() -> None:
    conteudo = _conteudo_python_backend().lower()
    assert any(termo in conteudo for termo in ("retry", "backoff", "tentativa")), (
        "Backend deve possuir estratégia explícita de retry/backoff."
    )


def test_backend_possui_protecao_de_falha_em_cascata() -> None:
    conteudo = _conteudo_python_backend().lower()
    assert any(termo in conteudo for termo in ("circuit_breaker", "circuit breaker", "disjuntor")), (
        "Backend deve possuir circuit breaker/disjuntor para integrações críticas."
    )
