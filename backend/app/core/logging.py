import logging
import logging.handlers
from pathlib import Path

import structlog

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


def configure_logging(debug: bool) -> None:
    LOG_DIR.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "backend.log", maxBytes=5_000_000, backupCount=5
    )
    console_handler = logging.StreamHandler()

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=[file_handler, console_handler],
    )

    # `actor`/`action`/`target` are reserved for future audit logging
    # (device write-operations in later versions) — unused but present now
    # so the event shape doesn't change when that lands.
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.EventRenamer("event"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name).bind(actor=None, action=None, target=None)
