from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from constants import EVENT_TOKEN_KEYS, TOKEN_SECRET_KEYS
from errors import ConfigError

_LOAD_DEBUG: dict[str, object] = {}


def load_secrets() -> dict[str, str]:
    global _LOAD_DEBUG
    loaded, debug = _from_samsarafnsecrets()
    _LOAD_DEBUG = debug
    if loaded:
        return loaded
    loaded, debug = _from_legacy_function()
    _LOAD_DEBUG = {**_LOAD_DEBUG, **debug}
    if loaded:
        return loaded
    return {}


def secrets_debug(secrets: Mapping[str, Any]) -> dict[str, object]:
    return {
        "secretsCount": len(secrets),
        "secretKeys": sorted(str(key) for key in secrets.keys()),
        **_LOAD_DEBUG,
    }


def _normalize(raw: Any) -> dict[str, str]:
    if not raw:
        return {}
    return {str(key): str(value) for key, value in dict(raw).items() if value is not None}


def _from_samsarafnsecrets() -> tuple[dict[str, str], dict[str, object]]:
    try:
        from samsarafnsecrets import apply_to_env, get_secrets
    except Exception as exc:
        return {}, {
            "secretsLoader": "samsarafnsecrets",
            "secretsLoad": "import_error",
            "secretsError": type(exc).__name__,
        }

    last_error: str | None = None
    attempts = (
        ("default", {}),
        ("force_refresh", {"force_refresh": True}),
    )
    for label, kwargs in attempts:
        try:
            raw = get_secrets(**kwargs) if kwargs else get_secrets()
        except TypeError:
            continue
        except Exception as exc:
            last_error = type(exc).__name__
            continue
        parsed = _normalize(raw)
        if not parsed:
            continue
        try:
            apply_to_env(raw)
        except Exception:
            pass
        return parsed, {
            "secretsLoader": "samsarafnsecrets",
            "secretsLoad": label,
        }
    return {}, {
        "secretsLoader": "samsarafnsecrets",
        "secretsLoad": "error" if last_error else "empty",
        "secretsError": last_error,
    }


def _from_legacy_function() -> tuple[dict[str, str], dict[str, object]]:
    try:
        import samsara

        raw = samsara.Function().secrets().load()
    except Exception as exc:
        return {}, {
            "legacyLoader": "samsara.Function",
            "legacyLoad": "error",
            "legacyError": type(exc).__name__,
        }
    parsed = _normalize(raw)
    if not parsed:
        return {}, {"legacyLoader": "samsara.Function", "legacyLoad": "empty"}
    return parsed, {"legacyLoader": "samsara.Function", "legacyLoad": "ok"}


def _first_secret(mapping: Mapping[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    if not mapping:
        return None
    lowered = {str(key).strip().lower(): value for key, value in mapping.items()}
    for key in keys:
        value = mapping.get(key)
        if value is None:
            value = lowered.get(key.lower())
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def resolve_token(
    secrets: Mapping[str, str] | None = None,
    environ: Mapping[str, str] | None = None,
    event: Mapping[str, Any] | None = None,
) -> str:
    env = environ if environ is not None else os.environ
    token = (
        _first_secret(secrets, TOKEN_SECRET_KEYS)
        or _first_secret(event, EVENT_TOKEN_KEYS)
        or _first_secret(env, TOKEN_SECRET_KEYS)
        or _first_secret(env, EVENT_TOKEN_KEYS)
    )
    if not token:
        raise ConfigError(
            "API token is required: add Event parameter api_key "
            "(Function Secrets are not visible to this run)"
        )
    return token
