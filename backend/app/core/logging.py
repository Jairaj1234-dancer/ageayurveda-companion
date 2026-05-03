import logging
import sys

from app.config import get_settings


def setup_logging() -> logging.Logger:
    settings = get_settings()
    level = logging.DEBUG if settings.debug else logging.INFO

    logger = logging.getLogger("ageayurveda")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
