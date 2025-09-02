# color_logger.py
import logging
import sys

RESET = "\033[0m"
LEVEL_COLORS = {
    logging.DEBUG:    "\033[92m",  # green
    logging.INFO:     "\033[94m",  # blue
    logging.WARNING:  "\033[93m",  # yellow
    logging.ERROR:    "\033[91m",  # red
    logging.CRITICAL: "\033[91m",  # red
}

class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLORS.get(record.levelno, "\033[90m")
        # Put the colored [LEVEL] in a custom field the format string can use
        record.levelprefix = f"{color}[{record.levelname}]{RESET}"
        return super().format(record)

def get_logger(name: str = "vpn", level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(level=logging.INFO,force=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # <- prevents double printing via root logger

    if not logger.handlers:   # <- don't add a second handler on reloads
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColorFormatter("%(levelprefix)s: %(message)s"))
        logger.addHandler(handler)

    return logger
