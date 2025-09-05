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
        record.levelprefix = f"{color}[{record.levelname}]{RESET}"
        # Shorten overly long module names
        record.modpath = f"{record.name}" if len(record.name) < 25 else record.name[-25:]
        return super().format(record)

DEFAULT_FORMAT = "%(levelprefix)s %(modpath)s: %(message)s"

def get_logger(name: str = "driftcove", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False
    if logger.handlers:
        # Already configured
        return logger
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorFormatter(DEFAULT_FORMAT))
    logger.addHandler(handler)
    logger.propagate = False
    return logger

def configure_uvicorn_logging():
    """Replace Uvicorn's default formatters with our ColorFormatter to avoid duplicate & uncolored output."""
    target_names = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
    ]
    for name in target_names:
        lg = logging.getLogger(name)
        for h in list(lg.handlers):
            # Replace formatter with colored one
            h.setFormatter(ColorFormatter(DEFAULT_FORMAT))
        # Avoid propagating into root (prevents double print)
        lg.propagate = False

def setup_logging(level: int = logging.INFO):
    root = logging.getLogger()
    # Drop existing handlers (only if they look like default StreamHandlers without our formatter)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)
    # Add colored root (for 3rd party libs too)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(ColorFormatter(DEFAULT_FORMAT))
    root.addHandler(sh)
    configure_uvicorn_logging()
    return get_logger(level=level)
