from __future__ import annotations

import random
import re
import time
from typing import Callable, Optional

from .base import DriverResponse
from . import error_classifier


def extract_status(error_str: Optional[str]) -> Optional[int]:
    """Extract integer HTTP status from an error string like 'HTTP 429: body' -> 429, else None."""
    if not error_str:
        return None
    m = re.search(r"\bHTTP\s+(\d+)\b", error_str, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def with_retry(
    fn: Callable[[], DriverResponse],
    *,
    max_attempts: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
) -> DriverResponse:
    """Retry a driver call fn() up to max_attempts on retryable errors."""
    attempts = 0
    while True:
        resp = fn()
        attempts += 1

        if resp.meta is None:
            resp.meta = {}
        else:
            resp.meta = dict(resp.meta)

        if not resp.error:
            resp.meta["retry_attempts"] = attempts
            return resp

        status = extract_status(resp.error)
        err_class = error_classifier.classify(status, resp.error)

        if resp.meta.get("stream_started"):
            resp.meta["retry_attempts"] = attempts
            resp.meta["error_class"] = err_class.value
            return resp

        if not error_classifier.is_retryable(err_class):
            resp.meta["retry_attempts"] = attempts
            resp.meta["error_class"] = err_class.value
            return resp

        if attempts >= max_attempts:
            resp.meta["retry_attempts"] = attempts
            resp.meta["error_class"] = err_class.value
            return resp

        attempt_idx = attempts - 1
        backoff = min(base_delay * (2 ** attempt_idx), max_delay) + random.uniform(0.0, 0.5)

        if err_class == error_classifier.ErrorClass.RATE_LIMIT:
            retry_after = error_classifier.parse_retry_after(resp.error)
            if retry_after is not None:
                backoff = max(backoff, retry_after)

        sleep(backoff)
