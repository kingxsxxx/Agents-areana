import sys
from pathlib import Path

from loguru import logger as loguru_logger

from ..config import settings


class Logger:
    def __init__(self) -> None:
        self.logger = loguru_logger
        self._configured = False
        self._configure()

    def _configure(self) -> None:
        if self._configured:
            return
        self.logger.remove()

        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

        self.logger.add(sys.stdout, format=fmt, level=settings.LOG_LEVEL, colorize=True)
        self.logger.add(
            str(log_path),
            format=fmt,
            level="DEBUG",
            rotation=settings.LOG_ROTATION,
            retention=settings.LOG_RETENTION,
            encoding="utf-8",
        )
        self.logger.add(
            str(log_path.parent / "error.log"),
            format=fmt,
            level="ERROR",
            rotation=settings.LOG_ROTATION,
            retention=settings.LOG_RETENTION,
            encoding="utf-8",
        )
        self._configured = True

    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs):
        self.logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs):
        self.logger.exception(message, **kwargs)


logger = Logger()
