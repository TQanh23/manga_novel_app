import logging
import sys
from collections.abc import Mapping, Sequence
from typing import Any, TextIO

import structlog
from structlog.typing import EventDict, Processor

REDACTED = "[redacted]"

# Keys whose values may carry manuscript text, prompts or model output. They are
# masked wherever they appear in a log event, at any depth (AI data policy: no
# prompt or output logging).
CONTENT_FIELDS = frozenset(
    {"text", "content", "messages", "input", "prompt", "output", "body_md", "body_html"}
)

_handler: logging.Handler | None = None


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: REDACTED
            if isinstance(key, str) and key.lower() in CONTENT_FIELDS
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_redact(item) for item in value]
    return value


def redact_content_fields(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """structlog processor: mask content fields before anything is rendered."""
    redacted: EventDict = _redact(event_dict)
    return redacted


def _drop_color_message(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    # uvicorn attaches an ANSI-coloured copy of its message as an extra.
    event_dict.pop("color_message", None)
    return event_dict


# Applied to structlog events and to records from stdlib loggers (uvicorn,
# alembic, sqlalchemy) alike, so every line has the same shape and filter.
_SHARED_PROCESSORS: list[Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.stdlib.ExtraAdder(),
    _drop_color_message,
    redact_content_fields,
]


def build_handler(stream: TextIO) -> logging.Handler:
    """A handler that writes one JSON object per line to the stream."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=_SHARED_PROCESSORS,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(ensure_ascii=False),
            ],
        )
    )
    return handler


def configure_logging(level: str = "INFO") -> None:
    """Route structlog and stdlib logging to JSON lines on stdout. Safe to call again."""
    global _handler

    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
    _handler = build_handler(sys.stdout)
    root.addHandler(_handler)
    root.setLevel(level.upper())

    # uvicorn and arq install their own handlers before they import our code.
    # Their loggers propagate to the root handler instead. The request
    # middleware writes the access line, so uvicorn's is switched off.
    for name in ("uvicorn", "uvicorn.error", "arq"):
        foreign_logger = logging.getLogger(name)
        foreign_logger.handlers.clear()
        foreign_logger.propagate = True
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
