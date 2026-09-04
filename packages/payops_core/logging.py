import logging
import sys

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide stdout logging. Safe to call more than once."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=_LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
