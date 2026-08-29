import argparse
import logging
import os
import signal
import threading

import app.models  # noqa: F401
from app.db import Base, SessionLocal, engine
from app.services.pentaho_integration import processar_proximo_lote, recuperar_lotes_abandonados

logger = logging.getLogger('reqsys.pentaho.worker')
_parar = threading.Event()


def _segundos_env(nome: str, padrao: float, minimo: float) -> float:
    valor = os.getenv(nome, str(padrao))
    try:
        numero = float(valor)
    except ValueError as exc:
        raise RuntimeError(f'{nome} deve ser numérico') from exc
    if numero < minimo:
        raise RuntimeError(f'{nome} deve ser maior ou igual a {minimo}')
    return numero


def _sinal_parada(signum, _frame) -> None:
    logger.info('pentaho_worker_shutdown_signal signal=%s', signum)
    _parar.set()


def executar_ciclo() -> dict[str, object]:
    db = SessionLocal()
    try:
        recuperacao = recuperar_lotes_abandonados(db)
        lote_id = processar_proximo_lote(db)
        return {
            'loteId': lote_id,
            'recuperados': recuperacao['recuperados'],
            'quarentena': recuperacao['quarentena'],
        }
    except Exception:
        db.rollback()
        logger.exception('pentaho_worker_cycle_failed')
        return {'loteId': None, 'recuperados': 0, 'quarentena': 0}
    finally:
        db.close()


def executar(*, uma_vez: bool = False) -> int:
    Base.metadata.create_all(bind=engine)
    intervalo = _segundos_env('REQSYS_PENTAHO_WORKER_POLL_SECONDS', 1.0, 0.1)
    logger.info('pentaho_worker_started poll_seconds=%s once=%s', intervalo, uma_vez)

    while not _parar.is_set():
        resultado = executar_ciclo()
        if resultado['loteId']:
            logger.info('pentaho_worker_batch_processed lote_id=%s', resultado['loteId'])
        if resultado['recuperados'] or resultado['quarentena']:
            logger.warning(
                'pentaho_worker_recovery recovered=%s quarantine=%s',
                resultado['recuperados'],
                resultado['quarentena'],
            )
        if uma_vez:
            return 0
        _parar.wait(intervalo)

    logger.info('pentaho_worker_stopped')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Consumidor durável da integração Pentaho → ReqSys')
    parser.add_argument('--once', action='store_true', help='executa um ciclo e encerra')
    args = parser.parse_args()

    logging.basicConfig(
        level=os.getenv('LOG_LEVEL', 'INFO').upper(),
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    signal.signal(signal.SIGTERM, _sinal_parada)
    signal.signal(signal.SIGINT, _sinal_parada)
    return executar(uma_vez=args.once)


if __name__ == '__main__':
    raise SystemExit(main())
