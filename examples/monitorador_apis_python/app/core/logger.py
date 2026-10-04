import logging
from pathlib import Path


def configurar_logger(diretorio_logs: Path) -> logging.Logger:
    diretorio_logs.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("monitorador_apis")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formato = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    arquivo_handler = logging.FileHandler(
        diretorio_logs / "monitorador.log",
        encoding="utf-8",
    )
    arquivo_handler.setFormatter(formato)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formato)

    logger.addHandler(arquivo_handler)
    logger.addHandler(console_handler)

    return logger
