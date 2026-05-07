"""Central logging configuration: routes all stdlib logging through loguru."""

import logging
import sys
from typing import Any, Callable

from loguru import logger


class _InterceptHandler(logging.Handler):
    """Redirect stdlib logging records (uvicorn, sqlalchemy, httpx, etc.) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _make_format(*, dev: bool) -> Callable[[Any], str]:
    def _format(record: Any) -> str:
        extra = record["extra"]
        ctx = ""
        if extra:
            parts = [
                f"{k}={str(v).replace('{', '{{').replace('}', '}}')}"
                for k, v in extra.items()
            ]
            ctx = " | " + " ".join(parts)

        if dev:
            return (
                "<green>{time:HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
                + ctx
                + "\n{exception}"
            )
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{line} | "
            "{message}"
            + ctx
            + "\n{exception}"
        )

    return _format


def configure_logging(level: str = "INFO", dev: bool = True) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format=_make_format(dev=dev),
        level=level,
        colorize=dev,
        backtrace=dev,
        diagnose=dev,
    )
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    # Suppress uvicorn's own access log — RequestLoggingMiddleware handles it with request_id
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    uvicorn_access.propagate = False
