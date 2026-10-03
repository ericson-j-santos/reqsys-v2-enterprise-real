from pathlib import Path
import importlib.util
import sys

import pytest

MODULE_PATH=Path(__file__).resolve().parents[2]/'scripts'/'ocr_benchmark.py'
spec=importlib.util.spec_from_file_location('ocr_benchmark',MODULE_PATH); mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)

def test_metricas_perfeitas():
    m=mod.calcular_metricas([{'expected':'MARIA SILVA','predicted':'MARIA SILVA','state':'AUTO'},{'expected':'JOÃO SANTOS','predicted':'JOAO SANTOS','state':'AUTO'}])
    assert m.cer == 0 and m.exact_match == 1 and m.false_auto == 0
    assert mod.avaliar_gate(m,exact_min=.98,cer_max=.005,false_auto_max=0) == []

def test_false_auto_bloqueia_gate():
    m=mod.calcular_metricas([{'expected':'MARIA SILVA','predicted':'MAR1A SILVA','state':'AUTO'}])
    assert m.false_auto == 1
    assert mod.avaliar_gate(m,exact_min=0,cer_max=1,false_auto_max=0)

def test_erro_em_revisao_nao_e_false_auto():
    m=mod.calcular_metricas([{'expected':'ILSON LIMA','predicted':'1LSON LIMA','state':'REVISAO'}])
    assert m.exact_match == 0 and m.false_auto == 0

def test_corpus_versionado_tem_ids_unicos_e_versao_canonica():
    corpus=mod.carregar_corpus_versionado()
    assert len(corpus) >= 8
    assert len({x['case_id'] for x in corpus}) == len(corpus)
    assert all(x['corpus_version'] == mod.CORPUS_VERSION for x in corpus)


def test_resolver_imagemagick_rejeita_convert_do_windows(monkeypatch):
    def fake_which(nome):
        return r'C:\\Windows\\System32\\convert.exe' if nome == 'convert' else None

    class Probe:
        returncode = 0
        stdout = 'Microsoft Windows File System Conversion Utility'
        stderr = ''

    monkeypatch.setattr(mod.shutil, 'which', fake_which)
    monkeypatch.setattr(mod.subprocess, 'run', lambda *args, **kwargs: Probe())

    with pytest.raises(RuntimeError, match='ImageMagick não encontrado'):
        mod._resolver_imagemagick()


def test_resolver_imagemagick_aceita_assinatura_valida(monkeypatch):
    monkeypatch.setattr(mod.shutil, 'which', lambda nome: '/usr/bin/magick' if nome == 'magick' else None)

    class Probe:
        returncode = 0
        stdout = 'Version: ImageMagick 7.1.1'
        stderr = ''

    monkeypatch.setattr(mod.subprocess, 'run', lambda *args, **kwargs: Probe())

    assert mod._resolver_imagemagick() == '/usr/bin/magick'
