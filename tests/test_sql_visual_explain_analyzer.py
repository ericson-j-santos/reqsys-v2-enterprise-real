from scripts.sql_visual_explain_analyzer import analyze_sql


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
