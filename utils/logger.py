
import logging
from logging.handlers import RotatingFileHandler

from utils.config import get_settings


def get_logger(name: str = "yukticorex") -> logging.Logger:
    """
    Create or return a configured application logger.

    Args:
        name: Logger name.

    Returns:
        logging.Logger: Configured logger instance.
    """

    settings = get_settings()

    logger = logging.getLogger(name)

    # Prevent duplicate handlers during repeated imports
    if getattr(logger, "_yukticorex_configured", False):
        return logger

    log_level = getattr(
        logging,
        settings.log_level,
        logging.INFO
    )

    logger.setLevel(log_level)
    logger.propagate = False

    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)

    logger.addHandler(console_handler)

    # File logging
    try:
        settings.log_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )

        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_format)

        logger.addHandler(file_handler)

    except OSError:
        logger.warning(
            "File logging unavailable. Using console logging only."
        )

    logger._yukticorex_configured = True

    return logger
