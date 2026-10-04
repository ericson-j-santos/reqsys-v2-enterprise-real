import sys
import zipfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MODULE_NAME = "gerador_solucao_completa_pentaho"
MODULE_PATH = (
    Path(__file__).parents[1]
    / "tools"
    / "gerador_pentaho"
    / "gerador_solucao_completa.py"
)
spec = spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert spec and spec.loader
gerador = module_from_spec(spec)
sys.modules[MODULE_NAME] = gerador
spec.loader.exec_module(gerador)

ARQUIVOS_ESPERADOS = {
    ".env.example",
    "CHANGELOG.md",
    "README.md",
    "dashboard.html",
    "docs/arquitetura-job-transformacao.md",
    "docs/extracao-e-analise.md",
    "docs/mapeamento-pentaho.md",
    "exemplos/demandas.csv",
    "exemplos/demandas.json",
    "package.json",
    "pentaho/config/treino.properties",
    "pentaho/executar-job.bat",
    "pentaho/executar-job.sh",
    "pentaho/jobs/jb_treino_criar_dossies.kjb",
    "pentaho/transformacoes/tr_criar_dossies_treino.ktr",
    "pentaho/transformacoes/tr_validar_configuracao.ktr",
    "src/executar-fluxo.js",
    "src/servidor-simulado.js",
    "testes/fluxo.test.js",
}


def test_dry_run_lista_arquivos_esperados(capsys):
    codigo = gerador.main(["--dry-run"])
    assert codigo == 0
    listados = set(capsys.readouterr().out.strip().splitlines())
    assert listados == ARQUIVOS_ESPERADOS


def test_gerar_diretorio_copia_conteudo_identico(tmp_path):
    destino = tmp_path / "app-gerada"
    raiz = gerador.gerar_diretorio(destino, forcar=False)

    assert raiz == destino
    gerados = {
        caminho.relative_to(destino).as_posix()
        for caminho in destino.rglob("*")
        if caminho.is_file()
    }
    assert gerados == ARQUIVOS_ESPERADOS

    original = gerador.PACOTE_DIR / "src" / "executar-fluxo.js"
    copia = destino / "src" / "executar-fluxo.js"
    assert copia.read_bytes() == original.read_bytes()


def test_gerar_diretorio_falha_sem_force_em_destino_existente(tmp_path):
    destino = tmp_path / "app-gerada"
    destino.mkdir()
    (destino / "marcador.txt").write_text("existente")

    with pytest.raises(gerador.ErroGeracao, match="DESTINO_JA_EXISTE"):
        gerador.gerar_diretorio(destino, forcar=False)

    # nao deve ter apagado o conteudo existente numa falha esperada
    assert (destino / "marcador.txt").exists()


def test_gerar_diretorio_com_force_sobrescreve(tmp_path):
    destino = tmp_path / "app-gerada"
    destino.mkdir()
    (destino / "marcador.txt").write_text("existente")

    gerador.gerar_diretorio(destino, forcar=True)

    assert not (destino / "marcador.txt").exists()
    assert (destino / "README.md").exists()


def test_gerar_zip_contem_todos_os_arquivos_com_prefixo(tmp_path):
    destino_zip = tmp_path / "pacote.zip"
    resultado = gerador.gerar_zip(destino_zip, forcar=False)

    assert resultado == destino_zip
    with zipfile.ZipFile(destino_zip) as arquivo_zip:
        nomes = set(arquivo_zip.namelist())
    esperados_com_prefixo = {
        f"{gerador.NOME_APLICACAO}/{relativo}" for relativo in ARQUIVOS_ESPERADOS
    }
    assert nomes == esperados_com_prefixo


def test_gerar_zip_falha_sem_force_em_destino_existente(tmp_path):
    destino_zip = tmp_path / "pacote.zip"
    destino_zip.write_bytes(b"conteudo previo")

    with pytest.raises(gerador.ErroGeracao, match="ZIP_JA_EXISTE"):
        gerador.gerar_zip(destino_zip, forcar=False)


def test_pacote_nao_contem_segredo_real():
    termos_suspeitos = ("senha=", "password=", "-----BEGIN")
    for caminho in gerador.PACOTE_DIR.rglob("*"):
        if not caminho.is_file():
            continue
        try:
            conteudo = caminho.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        for termo in termos_suspeitos:
            assert termo not in conteudo, f"{caminho}: termo suspeito {termo!r}"
