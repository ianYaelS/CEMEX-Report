from __future__ import annotations

from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout

from client import _is_retryable


def test_retryable_request_errors() -> None:
    assert _is_retryable(Timeout())
    assert _is_retryable(ConnectionError())
    assert _is_retryable(ChunkedEncodingError())
