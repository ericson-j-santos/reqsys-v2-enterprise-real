"""Testes do validador de idioma."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

CAMINHO_MODULO = Path(__file__).parents[1] / "scripts" / "validar_idioma.py"
ESPECIFICACAO = importlib.util.spec_from_file_location("validar_idioma", CAMINHO_MODULO)
assert ESPECIFICACAO and ESPECIFICACAO.loader
MODULO = importlib.util.module_from_spec(ESPECIFICACAO)
ESPECIFICACAO.loader.exec_module(MODULO)


class ValidarIdiomaTestes(unittest.TestCase):
    def setUp(self) -> None:
        self.temporario = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporario.name)
        self.contrato = {
            "idioma_principal": "pt-BR",
            "termos_de_dominio": {"request": "demanda", "dashboard": "painel"},
        }

    def tearDown(self) -> None:
        self.temporario.cleanup()

    def test_calcula_conformidade_por_arquivo(self) -> None:
        conforme = self.raiz / "conforme.py"
        aviso = self.raiz / "aviso.py"
        conforme.write_text("demanda = 1\n", encoding="utf-8")
        aviso.write_text("request = 1\n", encoding="utf-8")

        relatorio = MODULO.construir_relatorio(
            [str(conforme), str(aviso)], self.contrato, bloquear=False
        )

        self.assertEqual(relatorio["metricas"]["arquivos_analisados"], 2)
        self.assertEqual(relatorio["metricas"]["arquivos_com_aviso"], 1)
        self.assertEqual(relatorio["metricas"]["ocorrencias"], 1)
        self.assertEqual(relatorio["metricas"]["taxa_conformidade_percentual"], 50.0)

    def test_ignora_termo_contido_em_palavra(self) -> None:
        arquivo = self.raiz / "exemplo.py"
        arquivo.write_text("requested_at = None\n", encoding="utf-8")

        relatorio = MODULO.construir_relatorio(
            [str(arquivo)], self.contrato, bloquear=False
        )

        self.assertEqual(relatorio["metricas"]["ocorrencias"], 0)

    def test_grava_relatorio_json_em_portugues(self) -> None:
        arquivo = self.raiz / "exemplo.py"
        saida = self.raiz / "relatorio" / "idioma.json"
        arquivo.write_text("dashboard = {}\n", encoding="utf-8")

        relatorio = MODULO.construir_relatorio(
            [str(arquivo)], self.contrato, bloquear=False
        )
        MODULO.gravar_relatorio(saida, relatorio)
        persistido = json.loads(saida.read_text(encoding="utf-8"))

        self.assertEqual(persistido["idioma_principal"], "pt-BR")
        self.assertEqual(persistido["metricas"]["ocorrencias"], 1)
        self.assertEqual(persistido["ocorrencias"][0]["termo_canonico"], "painel")


if __name__ == "__main__":
    unittest.main()
