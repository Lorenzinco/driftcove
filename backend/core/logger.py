# logger_api.py
import logging
from backend.core.color_logger import get_logger

class Logger:
    def __init__(self, name: str = "vpn", level: int = logging.INFO):
        self._log = get_logger(name, level)

    def error(self, msg: str):   self._log.error(msg)
    def info(self, msg: str):    self._log.info(msg)
    def debug(self, msg: str):   self._log.debug(msg)
    def warning(self, msg: str): self._log.warning(msg)

logger = Logger()
