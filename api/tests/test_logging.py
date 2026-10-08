"""NFR-10 and the AI data policy: logs are JSON and never carry content fields."""

import logging
from collections.abc import Callable
from typing import Any

import structlog

from api.core.logging import CONTENT_FIELDS, REDACTED, redact_content_fields

LogLines = Callable[[], list[dict[str, Any]]]


def test_redaction_masks_every_content_field() -> None:
    event = {name: "an author's sentence" for name in CONTENT_FIELDS}

    assert redact_content_fields(None, "info", event) == {name: REDACTED for name in CONTENT_FIELDS}


def test_redaction_reaches_nested_dicts_and_lists() -> None:
    event = {
        "event": "consistency_check",
        "job": {
            "id": "j1",
            "tokens": 812,
            "request": {"prompt": "Tóm tắt chương 1", "model": "m"},
            "chunks": [{"id": 1, "text": "첫 번째 장"}, {"id": 2, "content": "第二章"}],
        },
        "Messages": [{"role": "user", "content": "x"}],
    }

    assert redact_content_fields(None, "info", event) == {
        "event": "consistency_check",
        "job": {
            "id": "j1",
            "tokens": 812,
            "request": {"prompt": REDACTED, "model": "m"},
            "chunks": [{"id": 1, "text": REDACTED}, {"id": 2, "content": REDACTED}],
        },
        "Messages": REDACTED,
    }


def test_redaction_leaves_other_values_alone() -> None:
    event = {"event": "indexed", "work_id": "w1", "chunk_count": 12, "tags": ["a", "b"]}

    assert redact_content_fields(None, "info", event) == event


def test_structlog_events_are_json_lines_with_content_masked(log_lines: LogLines) -> None:
    structlog.get_logger("test").info(
        "indexed", work_id="w1", text="Chương một", job={"output": "x"}
    )

    (line,) = [line for line in log_lines() if line["event"] == "indexed"]
    assert line["level"] == "info"
    assert line["work_id"] == "w1"
    assert line["text"] == REDACTED
    assert line["job"] == {"output": REDACTED}
    assert line["timestamp"].endswith("Z")


def test_stdlib_loggers_share_the_format_and_the_filter(log_lines: LogLines) -> None:
    logging.getLogger("uvicorn.error").warning(
        "worker %s started", 3, extra={"prompt": "secret", "color_message": "[36mworker[0m"}
    )

    (line,) = [line for line in log_lines() if line["event"] == "worker 3 started"]
    assert line["level"] == "warning"
    assert line["logger"] == "uvicorn.error"
    assert line["prompt"] == REDACTED
    assert "color_message" not in line
