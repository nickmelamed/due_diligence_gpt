from __future__ import annotations
import logging
from pathlib import Path

def setup_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger("ddgpt")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    fp = Path(log_path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(fp, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger
