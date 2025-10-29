"""Utilities for loading optional API keys used by the application."""
from __future__ import annotations

import os
import sys
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Optional, Tuple

from activity_logger import log_event, log_exception

_CACHED_KEYS_MODULE = None
_KEYS_MODULE_ATTEMPTED = False


def _load_local_keys_module():
    """Return the ``keys.py`` module located next to the sources if present."""

    global _CACHED_KEYS_MODULE, _KEYS_MODULE_ATTEMPTED

    if _KEYS_MODULE_ATTEMPTED:
        return _CACHED_KEYS_MODULE

    _KEYS_MODULE_ATTEMPTED = True

    keys_path = Path(__file__).with_name("keys.py")
    if not keys_path.exists():
        return None

    spec = spec_from_file_location("_app_keys", keys_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive branch
        return None

    module = module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as exc:  # pragma: no cover - defensive logging
        print(
            "Impossible d’importer keys.py à partir du chemin local :",
            exc,
            file=sys.stderr,
        )
        log_exception("CONFIG_KEYS", "Import local de keys.py impossible", exc, path=str(keys_path))
        return None

    _CACHED_KEYS_MODULE = module
    log_event("CONFIG_KEYS", "Module keys.py local chargé", path=str(keys_path))
    return module


def _load_module_attribute(name: str) -> Optional[str]:
    """Return the trimmed attribute ``name`` from ``keys.py`` if available."""

    keys_module = _load_local_keys_module()
    if keys_module is None:
        try:
            keys_module = import_module("keys")
        except ModuleNotFoundError:
            return None
        except Exception as exc:  # pragma: no cover - defensive logging
            print(
                "Impossible de charger le module keys.py :",
                exc,
                file=sys.stderr,
            )
            return None

    candidate = getattr(keys_module, name, None)
    if not candidate:
        log_event("CONFIG_KEYS", "Attribut manquant dans keys.py", attribute=name)
        return None

    trimmed = str(candidate).strip()
    if trimmed:
        log_event("CONFIG_KEYS", "Attribut chargé depuis keys.py", attribute=name)
    return trimmed or None


def load_semantic_scholar_api_key() -> Optional[str]:
    """Return the Semantic Scholar API key from the environment or ``keys.py``.

    The lookup order is:
    1. The ``SEMANTIC_SCHOLAR_API_KEY`` environment variable.
    2. A module named ``keys`` (located next to the application code) that
       exposes a ``SEMANTIC_SCHOLAR_API_KEY`` attribute.

    Empty strings are treated as missing values so that leaving the default
    placeholder unchanged in ``keys.py`` does not interfere with runtime
    configuration. Any unexpected error while importing ``keys`` is reported on
    ``stderr`` and ignored so the application can continue without a key.
    """

    env_value = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if env_value:
        trimmed = env_value.strip()
        if trimmed:
            log_event("CONFIG_KEYS", "Clé API chargée depuis l’environnement")
            return trimmed

    value = _load_module_attribute("SEMANTIC_SCHOLAR_API_KEY")
    if value:
        log_event("CONFIG_KEYS", "Clé API chargée depuis keys.py")
    return value


def load_tor_proxy() -> Optional[str]:
    """Return the Tor proxy URL from the environment or ``keys.py``."""

    for variable in ("TOR_SOCKS_PROXY", "TOR_PROXY"):
        value = os.getenv(variable)
        if value and value.strip():
            log_event("CONFIG_KEYS", "Proxy Tor récupéré depuis l’environnement", variable=variable)
            return value.strip()

    proxy_from_file = _load_module_attribute("TOR_SOCKS_PROXY")
    if proxy_from_file:
        log_event("CONFIG_KEYS", "Proxy Tor chargé depuis keys.py", attribute="TOR_SOCKS_PROXY")
        return proxy_from_file

    proxy_from_file = _load_module_attribute("TOR_PROXY")
    if proxy_from_file:
        log_event("CONFIG_KEYS", "Proxy Tor chargé depuis keys.py", attribute="TOR_PROXY")
        return proxy_from_file

    return None


def load_tor_browser_path() -> Optional[str]:
    """Return the Tor Browser directory if configured."""

    env_value = os.getenv("TOR_BROWSER_PATH")
    if env_value and env_value.strip():
        log_event("CONFIG_KEYS", "Chemin Tor Browser depuis l’environnement")
        return env_value.strip()

    value = _load_module_attribute("TOR_BROWSER_PATH")
    if value:
        log_event("CONFIG_KEYS", "Chemin Tor Browser depuis keys.py")
    return value


def load_tor_control_settings() -> Tuple[Optional[int], Optional[str]]:
    """Return the Tor control port and password if configured."""

    port_value: Optional[str] = None
    password_value: Optional[str] = None

    for variable in ("TOR_CONTROL_PORT",):
        value = os.getenv(variable)
        if value and value.strip():
            port_value = value.strip()
            log_event("CONFIG_KEYS", "Port de contrôle Tor depuis l’environnement")
            break

    if port_value is None:
        port_attr = _load_module_attribute("TOR_CONTROL_PORT")
        if port_attr:
            port_value = port_attr
            log_event("CONFIG_KEYS", "Port de contrôle Tor depuis keys.py")

    for variable in ("TOR_CONTROL_PASSWORD",):
        value = os.getenv(variable)
        if value and value.strip():
            password_value = value.strip()
            log_event("CONFIG_KEYS", "Mot de passe du port de contrôle depuis l’environnement")
            break

    if password_value is None:
        password_attr = _load_module_attribute("TOR_CONTROL_PASSWORD")
        if password_attr:
            password_value = password_attr
            log_event("CONFIG_KEYS", "Mot de passe du port de contrôle depuis keys.py")

    port: Optional[int] = None
    if port_value:
        try:
            port = int(port_value)
        except ValueError:
            log_event("CONFIG_KEYS", "Port de contrôle Tor invalide", value=port_value)
            port = None

    return port, password_value
