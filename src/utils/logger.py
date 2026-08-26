"""
Configurazione centralizzata del logging per tutto il progetto.

Uso in qualsiasi altro modulo:
    from logger import get_logger
    logger = get_logger(__name__)
    logger.info("messaggio")
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "daily_news.log"


def get_logger(name: str = "daily_news") -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger(name)

    # Evita di aggiungere handler duplicati se get_logger viene chiamato più volte
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Output su console (utile nei log di GitHub Actions)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Output su file (utile in locale; in Actions il filesystem è effimero
    # ma non fa male scriverlo comunque, puoi anche caricarlo come artifact)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger