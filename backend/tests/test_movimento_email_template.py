"""Testes de renderização do e-mail (HTML + fallback texto)."""
from datetime import date

from app.services.movimento_email.email_service import (
    build_email_movimento_message,
    render_email_movimento_html,
    render_email_movimento_text,
)
from app.services.email_mime_report_service import EmailIdentity
from app.services.movimento_email.models import (
    ContextoEmailMovimento,
    ItemFechamento,
    ItemPendenciaCadastro,
    ItemPendenciaHistorica,
    ItemPendenciaObservacao,
)


def _contexto_exemplo() -> ContextoEmailMovimento:
    return ContextoEmailMovimento(
        data_referencia=date(2026, 7, 24),
        correlation_id='corr-tpl-001',
        fechamento=[ItemFechamento(indicador='Propostas fechadas', valor='42', observacao='ok')],
        pendencias_cadastro=[
            ItemPendenciaCadastro(protocolo='P1', cliente='<script>alert(1)</script>', cpf='11122233344', pendencia='RG', dias_em_aberto=5)
        ],
        pendencias_historicas=[
            ItemPendenciaHistorica(periodo_referencia='2026-06', pendencia='RG', quantidade=8, percentual=9.876)
        ],
        pendencias_observacao=[
            ItemPendenciaObservacao(protocolo='P2', tipo_inconsistencia='Divergência', descricao='CPF divergente', etapa='Análise')
        ],
    )


def test_render_html_contem_secoes_e_dados():
    html = render_email_movimento_html(_contexto_exemplo())

    assert 'Fechamento diário' in html
    assert 'Propostas fechadas' in html
    assert 'Pendências de cadastramento' in html
    assert 'Pendências históricas' in html
    assert 'Pendências de observação/tratamento' in html
    assert 'corr-tpl-001' in html


def test_render_html_escapa_conteudo_hostil():
    html = render_email_movimento_html(_contexto_exemplo())

    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


def test_render_html_com_datasets_vazios_mostra_mensagem_padrao():
    contexto = ContextoEmailMovimento(data_referencia=date(2026, 7, 24), correlation_id='corr-vazio')

    html = render_email_movimento_html(contexto)

    assert 'Sem indicadores de fechamento' in html
    assert 'Sem pendências de cadastramento em aberto' in html


def test_render_text_contem_todas_as_secoes():
    texto = render_email_movimento_text(_contexto_exemplo())

    assert 'FECHAMENTO DIÁRIO' in texto
    assert 'PENDÊNCIAS DE CADASTRAMENTO' in texto
    assert 'PENDÊNCIAS HISTÓRICAS' in texto
    assert 'PENDÊNCIAS DE OBSERVAÇÃO/TRATAMENTO' in texto
    assert 'corr-tpl-001' in texto


def test_build_email_movimento_message_monta_mime_multipart():
    message = build_email_movimento_message(
        sender=EmailIdentity('robo@empresa.com', 'Robô Prospecção'),
        recipients=[EmailIdentity('analista@empresa.com')],
        contexto=_contexto_exemplo(),
    )

    assert message['Subject'] == 'Prospecção Movimento — Resumo diário 2026-07-24'
    assert message['X-Correlation-ID'] == 'corr-tpl-001'
    assert message.is_multipart()

    html_part = message.get_body(preferencelist=('html',))
    assert html_part is not None
    assert 'Fechamento diário' in html_part.get_content()
