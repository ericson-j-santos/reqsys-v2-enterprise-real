from pathlib import Path

from app.ocr.worker import EVENTO_OCR_SOLICITADO, OcrWorker, RepositorioResultadosOcrMemoria, registrar_ocr_worker
from app.services.runtime_core import RuntimeEventBus, RuntimeEventEnvelope, RuntimeEventStatus
from ocr_evidencia.dominio.nome import LeituraOCRNome, consensuar_nome

class MotorFake:
    def __init__(self, leituras=None):
        self.leituras = leituras or [LeituraOCRNome('MARIA APARECIDA SILVA', .995),LeituraOCRNome('MARIA APARECIDA SILVA', .994),LeituraOCRNome('MARIA APARECIDA SILVA', .993)]
    def processar(self, _entrada: Path, *, recorte=None):
        return consensuar_nome(self.leituras)

def evento(**overrides):
    payload={'document_ref':'doc.png','tipo_documento':'CIN','campo':'nome'}; payload.update(overrides)
    return RuntimeEventEnvelope(event_type=EVENTO_OCR_SOLICITADO,source='tests.ocr',aggregate_type='ocr_job',aggregate_id='OCR-0001',correlation_id='corr-ocr-001',payload=payload)

def test_worker_processa_nome_e_separa_pii_da_auditoria(tmp_path):
    (tmp_path/'doc.png').write_bytes(b'fake')
    repo=RepositorioResultadosOcrMemoria(); worker=OcrWorker(MotorFake(),repo,input_root=tmp_path); bus=RuntimeEventBus(); registrar_ocr_worker(bus,worker)
    entrega=bus.publish(evento())[0]; resultado=repo.obter('OCR-0001')
    assert entrega.status == RuntimeEventStatus.DELIVERED
    assert resultado is not None and resultado.valor == 'MARIA APARECIDA SILVA' and resultado.estado_ocr == 'AUTO'
    assert 'valor' not in resultado.auditoria_sem_pii()
    assert resultado.auditoria_sem_pii()['engine_version'] == '1.2.0'

def test_worker_rejeita_path_traversal_e_runtime_envia_dlq(tmp_path):
    repo=RepositorioResultadosOcrMemoria(); bus=RuntimeEventBus(); registrar_ocr_worker(bus,OcrWorker(MotorFake(),repo,input_root=tmp_path))
    entrega=bus.publish(evento(document_ref='../segredo.png'))[0]
    assert entrega.status == RuntimeEventStatus.DEAD_LETTER and 'OCR_INPUT_ROOT' in entrega.error
    assert repo.obter('OCR-0001') is None

def test_worker_rejeita_campo_ainda_nao_homologado(tmp_path):
    (tmp_path/'doc.png').write_bytes(b'fake')
    repo=RepositorioResultadosOcrMemoria(); bus=RuntimeEventBus(); registrar_ocr_worker(bus,OcrWorker(MotorFake(),repo,input_root=tmp_path))
    entrega=bus.publish(evento(campo='cpf'))[0]
    assert entrega.status == RuntimeEventStatus.DEAD_LETTER and 'somente campo nome' in entrega.error

def test_worker_rejeita_recorte_invalido(tmp_path):
    (tmp_path/'doc.png').write_bytes(b'fake')
    repo=RepositorioResultadosOcrMemoria(); bus=RuntimeEventBus(); registrar_ocr_worker(bus,OcrWorker(MotorFake(),repo,input_root=tmp_path))
    entrega=bus.publish(evento(recorte=[0,0,-1,20]))[0]
    assert entrega.status == RuntimeEventStatus.DEAD_LETTER and 'recorte inválido' in entrega.error
