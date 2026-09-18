import json
import sqlite3

conn = sqlite3.connect('reqsys.db')
cur = conn.cursor()

payload = json.dumps({
    'mudanca': 'endpoints_info_e_health_check',
    'status': 'aplicada',
    'data': '2026-05-01',
    'novos_endpoints': [
        '/v1/sistema/info',
        '/v1/sistema/health-check',
        '/v1/sistema/endpoints',
        '/v1/dashboard/info'
    ],
    'descricao': 'Adicionados endpoints de informação sobre a API, health check e documentação de endpoints'
}, ensure_ascii=True)

cur.execute(
    'INSERT INTO auditoria_eventos (correlation_id, usuario, acao, entidade, entidade_id, payload_minimo) VALUES (?,?,?,?,?,?)',
    ('chg-endpoints-info-20260501', 'copilot', 'ENDPOINTS_INFO_CRIADOS', 'api', 'reqsys-v2', payload)
)
conn.commit()

cur.execute('SELECT id, correlation_id, acao, criado_em FROM auditoria_eventos ORDER BY id DESC LIMIT 1')
resultado = cur.fetchone()
print(f"✅ Registro criado: ID {resultado[0]} - {resultado[2]} - {resultado[3]}")

conn.close()
