import logging

from src.gmb_mcp.config import get_log_level


def get_logger(name="gmb_mcp"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, get_log_level(), logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
