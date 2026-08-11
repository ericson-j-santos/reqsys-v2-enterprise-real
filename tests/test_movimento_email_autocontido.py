"""Testes de tools/geradores/movimento_email_autocontido.py (#2861) e do
dashboard autocontido em ops-dashboard/movimento-email/index.html.

Segue o mesmo padrão de tests/test_robo_envia_teamsv1_autocontido.py: carrega
o módulo via importlib (sem instalar nada), sem depender do backend/venv do
ReqSys — o próprio ponto do script é rodar sozinho.
"""
import os
import sys
import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_NAME = 'movimento_email_autocontido'
MODULE_PATH = Path(__file__).parents[1] / 'tools' / 'geradores' / 'movimento_email_autocontido.py'
spec = spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert spec and spec.loader
module = module_from_spec(spec)
sys.modules[MODULE_NAME] = module
spec.loader.exec_module(module)

DASHBOARD_HTML_PATH = Path(__file__).parents[1] / 'ops-dashboard' / 'movimento-email' / 'index.html'


def _contexto_exemplo():
    return module.ContextoEmailMovimento(
        data_referencia=date(2026, 7, 26),
        correlation_id='corr-teste-001',
        fechamento=[module.ItemFechamento(indicador='Propostas', valor='42', observacao='<script>alert(1)</script>')],
        pendencias_cadastro=[
            module.ItemPendenciaCadastro(protocolo='P1', cliente='Fulano', cpf='11122233344', pendencia='RG', dias_em_aberto=5)
        ],
        pendencias_historicas=[
            module.ItemPendenciaHistorica(periodo_referencia='2026-06', pendencia='RG', quantidade=8, percentual=9.876)
        ],
        pendencias_observacao=[
            module.ItemPendenciaObservacao(protocolo='P2', tipo_inconsistencia='Divergência', descricao='CPF divergente')
        ],
    )


class RenderizacaoTest(unittest.TestCase):
    def test_render_html_contem_secoes_e_escapa_conteudo_hostil(self):
        html_out = module.render_html(_contexto_exemplo())

        self.assertIn('Fechamento diário', html_out)
        self.assertIn('Pendências de cadastramento', html_out)
        self.assertIn('corr-teste-001', html_out)
        self.assertNotIn('<script>alert(1)</script>', html_out)
        self.assertIn('&lt;script&gt;', html_out)

    def test_render_html_vazio_mostra_mensagem_padrao(self):
        vazio = module.ContextoEmailMovimento(data_referencia=date(2026, 7, 26), correlation_id='corr-vazio')

        html_out = module.render_html(vazio)

        self.assertIn('Sem indicadores de fechamento', html_out)
        self.assertIn('Sem pendências de cadastramento em aberto', html_out)

    def test_render_texto_contem_todas_as_secoes(self):
        texto = module.render_texto(_contexto_exemplo())

        self.assertIn('FECHAMENTO DIÁRIO', texto)
        self.assertIn('PENDÊNCIAS DE CADASTRAMENTO', texto)
        self.assertIn('PENDÊNCIAS HISTÓRICAS', texto)
        self.assertIn('PENDÊNCIAS DE OBSERVAÇÃO/TRATAMENTO', texto)

    def test_montar_mensagem_mime(self):
        mensagem = module.montar_mensagem_mime(_contexto_exemplo(), remetente='robo@empresa.com', destinatarios=['a@b.com'])

        self.assertTrue(mensagem.is_multipart())
        self.assertEqual(mensagem['Subject'], 'Prospecção Movimento — Resumo diário 2026-07-26')
        self.assertEqual(mensagem['X-Correlation-ID'], 'corr-teste-001')


class MascaramentoTest(unittest.TestCase):
    def test_mascarar_email(self):
        self.assertEqual(module.mascarar_email('fulano@empresa.com'), 'f***@empresa.com')
        self.assertEqual(module.mascarar_email(None), '[DADO_MASCARADO]')
        self.assertEqual(module.mascarar_email('sem-arroba'), '[DADO_MASCARADO]')

    def test_mascarar_erro_remove_senha(self):
        detalhe = module._mascarar_erro('login falhou: password="segredo123"')
        self.assertNotIn('segredo123', detalhe)
        self.assertIn('[SEGREDO_REMOVIDO]', detalhe)


class CircuitBreakerRetryTest(unittest.TestCase):
    def test_call_with_retry_tenta_de_novo_ate_suceder(self):
        chamadas = {'n': 0}

        def _fn():
            chamadas['n'] += 1
            if chamadas['n'] < 3:
                raise ValueError('falha transitória')
            return 'ok'

        resultado = module.call_with_retry(_fn, max_retries=5, backoff_seconds=0, retry_on=(ValueError,))

        self.assertEqual(resultado, 'ok')
        self.assertEqual(chamadas['n'], 3)

    def test_circuit_breaker_abre_apos_falhas_consecutivas(self):
        circuito = module.CircuitBreaker(nome='teste', limite_falhas=2, cooldown_segundos=60)

        def _falha():
            raise ValueError('sempre falha')

        for _ in range(2):
            with self.assertRaises(ValueError):
                module.call_with_retry(_falha, max_retries=1, backoff_seconds=0, retry_on=(ValueError,), circuit=circuito)

        with self.assertRaises(module.CircuitBreakerOpenError):
            module.call_with_retry(_falha, max_retries=1, backoff_seconds=0, retry_on=(ValueError,), circuit=circuito)


class ClassificarSaudeTest(unittest.TestCase):
    def test_erro_prevalece_sobre_qualquer_outro_estado(self):
        contagens = {module.STATUS_PENDING: 0, module.STATUS_PROCESSING: 5, module.STATUS_SENT: 10, module.STATUS_ERROR: 1}
        self.assertEqual(module.classificar_saude(contagens), 'vermelho')

    def test_processing_sem_erro_e_azul(self):
        contagens = {module.STATUS_PENDING: 0, module.STATUS_PROCESSING: 1, module.STATUS_SENT: 0, module.STATUS_ERROR: 0}
        self.assertEqual(module.classificar_saude(contagens), 'azul')

    def test_pendente_ou_enviado_sem_erro_nem_processamento_e_verde(self):
        self.assertEqual(module.classificar_saude({module.STATUS_PENDING: 1, module.STATUS_PROCESSING: 0, module.STATUS_SENT: 0, module.STATUS_ERROR: 0}), 'verde')
        self.assertEqual(module.classificar_saude({module.STATUS_PENDING: 0, module.STATUS_PROCESSING: 0, module.STATUS_SENT: 3, module.STATUS_ERROR: 0}), 'verde')

    def test_fila_vazia_e_cinza(self):
        contagens = {module.STATUS_PENDING: 0, module.STATUS_PROCESSING: 0, module.STATUS_SENT: 0, module.STATUS_ERROR: 0}
        self.assertEqual(module.classificar_saude(contagens), 'cinza')


class ConstruirDashboardDataTest(unittest.TestCase):
    def test_monta_payload_com_schema_esperado_pelo_dashboard_html(self):
        contagens = {module.STATUS_PENDING: 2, module.STATUS_PROCESSING: 0, module.STATUS_SENT: 5, module.STATUS_ERROR: 0}
        itens = [{'id': 1, 'correlation_id': 'c1', 'assunto': 'A', 'status': 'SENT', 'retry_count': 0, 'created_at': 'x', 'sent_at': 'y'}]

        dados = module.construir_dashboard_data(contagens, itens)

        self.assertEqual(dados['schema_version'], '1.0.0')
        self.assertEqual(dados['contagens'], {'PENDING': 2, 'PROCESSING': 0, 'SENT': 5, 'ERROR': 0})
        self.assertEqual(dados['saude'], 'verde')
        self.assertEqual(dados['itens_recentes'], itens)
        self.assertIn('generated_at', dados)
        datetime.fromisoformat(dados['generated_at'])  # não levanta ValueError

    def test_preenche_contagens_ausentes_com_zero(self):
        dados = module.construir_dashboard_data({}, [])
        self.assertEqual(dados['contagens'], {'PENDING': 0, 'PROCESSING': 0, 'SENT': 0, 'ERROR': 0})
        self.assertEqual(dados['saude'], 'cinza')


class FilaSqliteTest(unittest.TestCase):
    """Máquina de estados da fila (sqlite3 local) — equivalente ao
    queue_repository.py do backend, incluindo a limpeza de reservas travadas
    (instrução global obrigatória: timeout, log quando libera)."""

    def setUp(self):
        self.caminho_db = tempfile.mktemp(suffix='.sqlite3')
        self.cfg = module.Config(queue_db_path=self.caminho_db)
        self.conexao = module._conectar_fila(self.cfg)

    def tearDown(self):
        self.conexao.close()
        if os.path.exists(self.caminho_db):
            os.remove(self.caminho_db)

    def _enfileirar(self, correlation_id='corr-001', max_retries=5):
        return module.enfileirar(
            self.conexao, correlation_id=correlation_id, data_referencia=date(2026, 7, 26),
            destinatarios=['a@b.com'], assunto='Assunto', html_body='<p>x</p>', text_body='x', max_retries=max_retries,
        )

    def test_enfileirar_cria_item_pending(self):
        item_id = self._enfileirar()
        snap = module.snapshot(self.conexao)
        self.assertEqual(item_id, 1)
        self.assertEqual(snap[module.STATUS_PENDING], 1)

    def test_reservar_lote_marca_processing_e_respeita_limite(self):
        for i in range(3):
            self._enfileirar(f'corr-{i}')

        lote = module.reservar_lote(self.conexao, lote_max=2)

        self.assertEqual(len(lote), 2)
        self.assertTrue(all(item['status'] == module.STATUS_PROCESSING for item in lote))

    def test_limpar_reservas_travadas_libera_apos_timeout_e_ignora_recentes(self):
        id_travado = self._enfileirar('corr-travado')
        id_recente = self._enfileirar('corr-recente')
        limite_antigo = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
        limite_recente = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
        self.conexao.execute('UPDATE movimento_email_dispatch SET status = ?, reserved_at = ? WHERE id = ?',
                              (module.STATUS_PROCESSING, limite_antigo, id_travado))
        self.conexao.execute('UPDATE movimento_email_dispatch SET status = ?, reserved_at = ? WHERE id = ?',
                              (module.STATUS_PROCESSING, limite_recente, id_recente))
        self.conexao.commit()

        liberadas = module.limpar_reservas_travadas(self.conexao, timeout_minutos=15)

        self.assertEqual(liberadas, 1)
        snap = module.snapshot(self.conexao)
        self.assertEqual(snap[module.STATUS_PENDING], 1)
        self.assertEqual(snap[module.STATUS_PROCESSING], 1)

    def test_marcar_enviado(self):
        item_id = self._enfileirar()
        module.marcar_enviado(self.conexao, item_id)

        snap = module.snapshot(self.conexao)
        self.assertEqual(snap[module.STATUS_SENT], 1)

    def test_marcar_erro_reagenda_ate_atingir_max_tentativas(self):
        self._enfileirar(max_retries=2)
        lote = module.reservar_lote(self.conexao, lote_max=1)
        item = lote[0]

        novo_status = module.marcar_erro(self.conexao, item, 'falha 1')
        self.assertEqual(novo_status, module.STATUS_PENDING)

        lote2 = module.reservar_lote(self.conexao, lote_max=1)
        novo_status2 = module.marcar_erro(self.conexao, lote2[0], 'falha 2')
        self.assertEqual(novo_status2, module.STATUS_ERROR)

    def test_listar_recentes_ordena_do_mais_novo_e_respeita_limite(self):
        for i in range(5):
            self._enfileirar(f'corr-{i}')

        recentes = module.listar_recentes(self.conexao, limite=2)

        self.assertEqual(len(recentes), 2)
        self.assertEqual(recentes[0]['correlation_id'], 'corr-4')
        self.assertNotIn('html_body', recentes[0])
        self.assertNotIn('destinatarios', recentes[0])


class DashboardHtmlAutocontidoTest(unittest.TestCase):
    """O dashboard tem que existir, ser autocontido (sem CDN externo) e
    consumir exatamente o schema que construir_dashboard_data produz."""

    def test_arquivo_existe(self):
        self.assertTrue(DASHBOARD_HTML_PATH.is_file(), f'{DASHBOARD_HTML_PATH} não encontrado')

    def test_sem_recurso_externo_cdn(self):
        conteudo = DASHBOARD_HTML_PATH.read_text(encoding='utf-8')
        self.assertNotIn('cdn.', conteudo.lower())
        self.assertNotIn('<script src="http', conteudo)
        self.assertNotIn('<link ', conteudo)  # nenhum stylesheet/font externo

    def test_consome_data_json_local(self):
        conteudo = DASHBOARD_HTML_PATH.read_text(encoding='utf-8')
        self.assertIn("fetch('./data.json'", conteudo)

    def test_referencia_as_quatro_chaves_de_status(self):
        conteudo = DASHBOARD_HTML_PATH.read_text(encoding='utf-8')
        for chave in ('PENDING', 'PROCESSING', 'SENT', 'ERROR'):
            self.assertIn(chave, conteudo)

    def test_nao_publica_dado_sensivel_hardcoded(self):
        conteudo = DASHBOARD_HTML_PATH.read_text(encoding='utf-8')
        self.assertNotIn('html_body', conteudo)
        self.assertNotIn('destinatarios', conteudo)


class CmdDashboardIntegracaoTest(unittest.TestCase):
    """cmd_dashboard fim a fim: fila sqlite -> data.json no formato esperado."""

    def setUp(self):
        self.caminho_db = tempfile.mktemp(suffix='.sqlite3')
        self.caminho_saida = tempfile.mktemp(suffix='.json')

    def tearDown(self):
        for caminho in (self.caminho_db, self.caminho_saida):
            if os.path.exists(caminho):
                os.remove(caminho)

    def test_cmd_dashboard_grava_json_valido(self):
        import json

        cfg = module.Config(queue_db_path=self.caminho_db)
        conexao = module._conectar_fila(cfg)
        module.enfileirar(conexao, correlation_id='corr-1', data_referencia=date(2026, 7, 26),
                           destinatarios=['a@b.com'], assunto='Assunto', html_body='<p>x</p>', text_body='x', max_retries=5)
        conexao.close()

        args = type('Args', (), {'output': self.caminho_saida, 'limite': 20})()
        os.environ['MOVIMENTO_EMAIL_QUEUE_DB_PATH'] = self.caminho_db
        try:
            codigo = module.cmd_dashboard(args)
        finally:
            del os.environ['MOVIMENTO_EMAIL_QUEUE_DB_PATH']

        self.assertEqual(codigo, 0)
        with open(self.caminho_saida, encoding='utf-8') as f:
            dados = json.loads(f.read())
        self.assertEqual(dados['contagens']['PENDING'], 1)
        self.assertEqual(dados['saude'], 'verde')
        self.assertEqual(len(dados['itens_recentes']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
