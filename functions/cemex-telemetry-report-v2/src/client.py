from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from errors import ApiError

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
# Functions ships a slim requests that does not always re-export these on the package.
try:
    from requests.exceptions import ChunkedEncodingError
except ImportError:  # pragma: no cover
    ChunkedEncodingError = type("ChunkedEncodingError", (RequestException,), {})

_RETRYABLE_REQUEST_ERRORS: tuple[type[BaseException], ...] = (
    Timeout,
    ConnectionError,
    ChunkedEncodingError,
)


class RetryableApiError(ApiError):
    """Transient HTTP error that may be retried."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RetryableApiError):
        return True
    return isinstance(exc, _RETRYABLE_REQUEST_ERRORS)


def _error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error")
        if message:
            return f"HTTP {response.status_code}: {message}"
    return f"HTTP {response.status_code}"


class SamsaraClient:
    def __init__(
        self,
        api_base_url: str,
        token: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/") + "/"
        self._token = token
        self._session = session or requests.Session()
        self.timeout = timeout

    def close(self) -> None:
        self._session.close()

    def request_json(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request_json_with_retry(method, path, params)

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _request_json_with_retry(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None,
    ) -> dict[str, Any]:
        url = urljoin(self.api_base_url, path.lstrip("/"))
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
        except _RETRYABLE_REQUEST_ERRORS:
            raise
        except RequestException as exc:
            raise ApiError(f"request failed for {path}") from exc

        if response.status_code in RETRY_STATUS:
            raise RetryableApiError(f"{path}: {_error_message(response)}", response.status_code)
        if response.status_code >= 400:
            raise ApiError(f"{path}: {_error_message(response)}", response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError(f"invalid JSON from {path}") from exc
        if not isinstance(payload, dict):
            raise ApiError(f"unexpected JSON payload from {path}")
        return payload

    def get_paginated(
        self,
        path: str,
        params: dict[str, str],
        merge_page: Callable[[list[Any], dict[str, Any]], None],
    ) -> list[Any]:
        query = dict(params)
        collected: list[Any] = []
        while True:
            payload = self.request_json("GET", path, query)
            merge_page(collected, payload)
            pagination = payload.get("pagination") or {}
            if not pagination.get("hasNextPage"):
                return collected
            cursor = pagination.get("endCursor")
            if not cursor:
                return collected
            query["after"] = str(cursor)
