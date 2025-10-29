import os
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from activity_logger import log_event


def configure_session_for_tor(
    session: requests.Session,
    explicit_proxy: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Configure the given session to use a Tor proxy if environment variables are set.

    Returns a tuple ``(using_tor, normalized_proxy_label)`` so callers can expose the
    resulting status in the interface or logs.
    """
    proxies: Dict[str, str] = {}

    socks_proxy = explicit_proxy or os.getenv("TOR_SOCKS_PROXY")
    http_proxy = os.getenv("TOR_PROXY") if explicit_proxy is None else None

    if socks_proxy:
        proxies["http"] = socks_proxy
        proxies["https"] = socks_proxy

    if http_proxy:
        proxies["http"] = http_proxy

    if not proxies:
        log_event("NETWORK", "Aucun proxy Tor configuré")
        return False, None

    session.proxies.update(proxies)

    normalized = {}
    for scheme_key, proxy_url in proxies.items():
        parsed = urlparse(proxy_url)
        if parsed.hostname:
            scheme = parsed.scheme or ("socks5h" if scheme_key == "https" else "socks5")
            port = f":{parsed.port}" if parsed.port else ""
            normalized[scheme_key] = f"{scheme}://{parsed.hostname}{port}"
        else:
            normalized[scheme_key] = proxy_url

    log_event("NETWORK", "Session configurée pour Tor", proxies=normalized)
    # Prefer https proxy label for UI because it preserves socks configuration
    label_source = proxies.get("https") or proxies.get("http")
    label_parsed = urlparse(label_source) if label_source else None
    if label_parsed and label_parsed.hostname:
        scheme = label_parsed.scheme or "socks5h"
        port = f":{label_parsed.port}" if label_parsed.port else ""
        label = f"{scheme}://{label_parsed.hostname}{port}"
    else:
        label = label_source
    return True, label
