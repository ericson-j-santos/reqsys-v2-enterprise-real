from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_sql_visual_explain_complementa_query_intelligence_sem_banco() -> None:
    analyzer = read("scripts/sql_visual_explain_analyzer.py")
    query_intelligence = read("frontend/src/services/queryIntelligence.js")

    assert "export function analyzeSql" in query_intelligence
    assert "não abre conexão com banco" in analyzer
    assert "não executa SQL" in analyzer
    assert "EXPLAIN/EXPLAIN ANALYZE" in analyzer
    assert "psycopg" not in analyzer.lower()
    assert "sqlalchemy" not in analyzer.lower()


def test_lab_declara_limites_operacionais() -> None:
    lab = read("public/sql-visual-explain-lab.html")

    assert "Laboratório estático" in lab
    assert "não executa SQL" in lab
    assert "não produz evidência de performance" in lab
