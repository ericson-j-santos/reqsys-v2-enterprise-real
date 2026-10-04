from scripts.sql_visual_explain_analyzer import analyze_sql, normalize_sql, render_markdown, render_mermaid


def test_analyze_sql_extracts_core_parts():
    sql = """
    SELECT u.id, u.name, o.total
    FROM users u
    JOIN orders o ON o.user_id = u.id
    WHERE o.total > 100
    ORDER BY o.total DESC;
    """

    analysis = analyze_sql(sql)

    assert analysis.tables == ["users"]
    assert analysis.joins == ["orders ON o.user_id = u.id"]
    assert analysis.filters == ["o.total > 100"]
    assert analysis.order_by == ["o.total DESC"]
    assert analysis.destructive_commands == []


def test_analyzer_remove_comentarios_e_detecta_comandos_destrutivos_sem_executar():
    sql = """
    -- exemplo controlado
    DELETE FROM clientes WHERE id = 1;
    """

    assert normalize_sql(sql) == "DELETE FROM clientes WHERE id = 1;"
    analysis = analyze_sql(sql)

    assert analysis.destructive_commands == ["DELETE"]
    report = render_markdown(sql, analysis)
    assert "não executa SQL nem EXPLAIN ANALYZE" in report
    assert "`DELETE`" in report


def test_render_mermaid_e_deterministico():
    analysis = analyze_sql(
        "SELECT u.id FROM users u JOIN orders o ON o.user_id = u.id WHERE o.total > 100"
    )

    assert render_mermaid(analysis) == (
        'flowchart LR\n'
        '  users["users"]\n'
        '  orders["orders"]\n'
        '  users --> orders'
    )
