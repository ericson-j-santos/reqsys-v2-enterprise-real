"""Bounded context OCR do ReqSys."""
from .worker import EVENTO_OCR_SOLICITADO, MotorOcrEvidencia, OcrWorker, RepositorioResultadosOcrMemoria, registrar_ocr_worker
__all__ = ['EVENTO_OCR_SOLICITADO','MotorOcrEvidencia','OcrWorker','RepositorioResultadosOcrMemoria','registrar_ocr_worker']
