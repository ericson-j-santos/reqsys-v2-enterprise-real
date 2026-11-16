#!/usr/bin/env python3
"""Contrato de portabilidade Git: a árvore versionada não pode colidir no Windows."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADICIONAL = "docs/adr/ADR-0001-padrao-ouro-enterprise.md"
INDICE = "docs/adr/INDEX.md"
ANTIGO = "docs/ADR/"


def encontrar_colisoes(caminhos: list[str]) -> list[tuple[str, str]]:
    """Compara todos os prefixos, não só nomes completos de arquivos."""
    vistos: dict[str, str] = {}
    colisoes: set[tuple[str, str]] = set()
    for caminho in caminhos:
        segmentos = caminho.replace("\\", "/").split("/")
        for limite in range(1, len(segmentos) + 1):
            original = "/".join(segmentos[:limite])
            chave = original.casefold()
            anterior = vistos.setdefault(chave, original)
            if anterior != original:
                colisoes.add(tuple(sorted((anterior, original))))
    return sorted(colisoes)


def arquivos_do_git() -> list[str]:
    resultado = subprocess.run(
        ["git", "ls-tree", "-rz", "--name-only", "HEAD"],
        cwd=ROOT, check=True, capture_output=True,
    )
    return [x.decode("utf-8") for x in resultado.stdout.split(b"\0") if x]


class TestPortabilidadeWindows(unittest.TestCase):
    def test_negativo_pastas_diferem_apenas_na_caixa(self) -> None:
        colisoes = encontrar_colisoes(["docs/ADR/um.md", "docs/adr/dois.md"])
        self.assertIn(("docs/ADR", "docs/adr"), colisoes)

    def test_negativo_arquivo_com_outra_caixa(self) -> None:
        self.assertTrue(encontrar_colisoes(["docs/adr/INDEX.md", "docs/adr/index.md"]))

    def test_positivo_arvore_normalizada(self) -> None:
        self.assertEqual(encontrar_colisoes(
            ["docs/adr/um.md", "docs/adr/dois.md"]), [])

    def test_checkout_real_sem_colisao_de_caixa(self) -> None:
        caminhos = arquivos_do_git()
        self.assertGreater(len(caminhos), 100, "Git não retornou a árvore real")
        self.assertEqual(encontrar_colisoes(caminhos), [])
        self.assertIn(ADICIONAL, caminhos)
        self.assertIn(INDICE, caminhos)
        self.assertFalse(any(caminho.startswith(ANTIGO) for caminho in caminhos))

    def test_referencias_ativas_apontam_para_arvore_portavel(self) -> None:
        workflow = (ROOT / ".github/workflows/governanca-padrao-ouro.yml").read_text(
            encoding="utf-8")
        inventario = (ROOT / "docs/architecture/trilha-e/inventory.json").read_text(
            encoding="utf-8")
        for conteudo in (workflow, inventario):
            self.assertIn(ADICIONAL, conteudo)
            self.assertNotIn("docs/ADR/ADR-0001-padrao-ouro-enterprise.md", conteudo)
        self.assertTrue((ROOT / ADICIONAL).is_file())
        self.assertTrue((ROOT / INDICE).is_file())


if __name__ == "__main__":
    unittest.main()
