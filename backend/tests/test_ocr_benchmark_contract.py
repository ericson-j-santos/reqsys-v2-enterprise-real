from pathlib import Path
import importlib.util
import sys

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
