"""What an error may say. Users get a generic line with a reference; the detail stays in the log."""
from __future__ import annotations

import logging
import re
import secrets

# Query parameters that carry a credential: API keys, and the SAS tokens on signed archive URLs.
_SECRET_PARAM = re.compile(
    r"(?i)\b(api[_-]?key|key|token|access_token|sig|signature|skoid|sktid|skt|ske|sks|skv|sv|se|st|sp|sr)"
    r"=[^&\s\"'<>]+"
)
_RAW_ERROR = re.compile(r"[A-Za-z]\w*(?:Error|Exception|Timeout)\b|https?://|Traceback|File \"")
RUN_STOPPED = "The run stopped unexpectedly."


def scrub(text: object) -> str:
    return _SECRET_PARAM.sub(r"\1=[removed]", str(text))


def new_ref() -> str:
    return secrets.token_hex(4)


def report(log: logging.Logger, context: str, exc: BaseException) -> str:
    """Logs the detail against a new reference and returns the reference for the user."""
    ref = new_ref()
    log.error("%s [ref %s]: %s: %s", context, ref, type(exc).__name__, scrub(exc))
    return ref


def public_text(text: str | None, fallback: str = RUN_STOPPED) -> str | None:
    """Text stored by an older version may hold an exception or a URL. Nothing raw is shown."""
    if not text:
        return text
    return fallback if _RAW_ERROR.search(text) else scrub(text)


class ScrubbingFormatter(logging.Formatter):
    """A signed URL or key inside an exception message never reaches the log file."""

    def format(self, record: logging.LogRecord) -> str:
        return scrub(super().format(record))
