from pathlib import Path
import importlib.util
import sys

MODULE_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'ocr_dataset_policy.py'
spec = importlib.util.spec_from_file_location('ocr_dataset_policy', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_ibge_permitido_no_ci_corporativo_sem_aceite():
    result = mod.avaliar_dataset('ibge-nomes', contexto='corporate-ci', aceite_humano=False)
    assert result['allowed'] is True


def test_datasets_restritos_bloqueados_no_ci_corporativo():
    for dataset_id in ('midv-2020', 'xfund-pt', 'funsd'):
        result = mod.avaliar_dataset(dataset_id, contexto='corporate-ci', aceite_humano=True)
        assert result['allowed'] is False
        assert result['reason'] == 'CONTEXT_NOT_LICENSED'


def test_research_exige_aceite_humano_e_entao_libera():
    for dataset_id in ('midv-2020', 'xfund-pt', 'funsd'):
        blocked = mod.avaliar_dataset(dataset_id, contexto='research-noncommercial', aceite_humano=False)
        assert blocked['allowed'] is False
        assert blocked['reason'] == 'HUMAN_LICENSE_ACCEPTANCE_REQUIRED'
        allowed = mod.avaliar_dataset(dataset_id, contexto='research-noncommercial', aceite_humano=True)
        assert allowed['allowed'] is True


def test_dataset_desconhecido_falha_fechado():
    result = mod.avaliar_dataset('nao-existe', contexto='research-noncommercial', aceite_humano=True)
    assert result == {
        'allowed': False,
        'reason': 'DATASET_UNKNOWN',
        'dataset_id': 'nao-existe',
        'context': 'research-noncommercial',
    }
