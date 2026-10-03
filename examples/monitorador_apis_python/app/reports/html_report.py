from pathlib import Path

from app.domain.models import ResultadoMonitoramento


def gerar_relatorio_html(
    resultados: list[ResultadoMonitoramento],
    caminho_saida: Path,
) -> Path:
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    linhas = []

    for item in resultados:
        cor = {
            "VERDE": "#dcfce7",
            "AMARELO": "#fef9c3",
            "VERMELHO": "#fee2e2",
        }.get(item.status_operacional, "#f3f4f6")

        linhas.append(
            f"""
            <tr style="background:{cor}">
                <td>{item.nome}</td>
                <td>{item.url}</td>
                <td>{item.status_code or "-"}</td>
                <td>{item.status_operacional}</td>
                <td>{item.tempo_resposta_ms:.2f}</td>
                <td>{item.erro or ""}</td>
            </tr>
            """
        )

    html = f"""
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Relatório Monitorador de APIs</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 32px; background: #f8fafc; color: #111827; }}
        h1 {{ margin-bottom: 8px; }}
        .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ border: 1px solid #e5e7eb; padding: 10px; text-align: left; font-size: 14px; }}
        th {{ background: #111827; color: white; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Relatório Monitorador de APIs</h1>
        <p>Semáforo: VERDE até 1000ms, AMARELO até 2500ms, VERMELHO para falha ou lentidão crítica.</p>
        <table>
            <thead>
                <tr>
                    <th>API</th>
                    <th>URL</th>
                    <th>HTTP</th>
                    <th>Status</th>
                    <th>Tempo ms</th>
                    <th>Erro</th>
                </tr>
            </thead>
            <tbody>
                {''.join(linhas)}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    caminho_saida.write_text(html, encoding="utf-8")
    return caminho_saida
