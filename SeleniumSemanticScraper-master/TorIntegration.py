"""Integration helpers to launch Tor Browser via ``tor-browser-selenium``."""
from __future__ import annotations

import atexit
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from activity_logger import log_event, log_exception

try:  # Imported lazily so bootstrap can install dependencies first
    import tbselenium.common as cm
    from tbselenium.utils import launch_tbb_tor_with_stem
    from selenium.webdriver.common.utils import is_connectable
except Exception:  # pragma: no cover - modules are optional until bootstrap runs
    cm = None  # type: ignore[assignment]
    launch_tbb_tor_with_stem = None  # type: ignore[assignment]
    is_connectable = None  # type: ignore[assignment]

try:  # Optional dependency used for NEWNYM requests
    from stem import Signal
    from stem.control import Controller
except Exception:  # pragma: no cover - stem already listed as dependency but stay defensive
    Signal = None  # type: ignore[assignment]
    Controller = None  # type: ignore[assignment]


@dataclass
class TorProcessManager:
    """Manage a Tor process started from a Tor Browser bundle."""

    browser_path: Path
    process: Optional["subprocess.Popen[bytes]"] = None
    proxy_url: Optional[str] = None

    def start(self) -> Optional[str]:
        import time

        if launch_tbb_tor_with_stem is None or cm is None:
            print(
                "Le module tor-browser-selenium n’est pas disponible. Impossible de démarrer Tor automatiquement.",
                file=sys.stderr,
            )
            log_event("TOR_START", "Module tor-browser-selenium indisponible")
            return None

        if not self.browser_path.exists():
            print(
                f"Chemin Tor Browser introuvable : {self.browser_path}. Configurez TOR_BROWSER_PATH dans keys.py ou via l’environnement.",
                file=sys.stderr,
            )
            log_event("TOR_START", "Chemin Tor Browser introuvable", path=str(self.browser_path))
            return None

        if is_connectable is not None and is_connectable(cm.STEM_SOCKS_PORT):
            proxy = f"socks5h://127.0.0.1:{cm.STEM_SOCKS_PORT}"
            print(
                "Un service Tor utilise déjà le port réservé aux sessions Stem. L’application réutilisera ce proxy.",
            )
            self.proxy_url = proxy
            log_event("TOR_START", "Service Tor déjà disponible", proxy=proxy)
            return proxy

        print("Démarrage du service Tor intégré…")
        try:
            self.process = launch_tbb_tor_with_stem(tbb_path=str(self.browser_path))
        except Exception as exc:  # pragma: no cover - defensive logging
            print(
                "Impossible de lancer Tor Browser automatiquement :",
                exc,
                file=sys.stderr,
            )
            log_exception("TOR_START", "Échec du démarrage automatique de Tor", exc)
            return None

        proxy = f"socks5h://127.0.0.1:{cm.STEM_SOCKS_PORT}"
        self.proxy_url = proxy

        # Attendre que le port soit accessible afin d’éviter des erreurs immédiates.
        if is_connectable is not None:
            for _ in range(30):
                if is_connectable(cm.STEM_SOCKS_PORT):
                    break
                time.sleep(1)

        print(f"Service Tor prêt. Proxy disponible sur {proxy}.")
        log_event("TOR_START", "Service Tor intégré prêt", proxy=proxy)

        atexit.register(self.stop)
        return proxy

    def stop(self) -> None:
        if self.process is None:
            return

        proc = self.process
        self.process = None
        try:
            proc.terminate()
            log_event("TOR_STOP", "Arrêt du service Tor demandé")
        except Exception as exc:  # pragma: no cover - defensive cleanup
            log_exception("TOR_STOP", "Échec de l’arrêt du service Tor", exc)
            return
        else:
            log_event("TOR_STOP", "Processus Tor arrêté")


_tor_manager: Optional[TorProcessManager] = None
_tor_checked = False
_tor_prereqs_logged = False
_tor_guidance_logged = False


def _report_tor_prerequisites() -> None:
    global _tor_prereqs_logged
    if _tor_prereqs_logged:
        return

    _tor_prereqs_logged = True

    platform = sys.platform
    if platform.startswith("linux"):
        log_event("TOR_PREREQ", "Plateforme Linux détectée pour tor-browser-selenium", platform=platform)
    elif platform == "darwin":
        log_event(
            "TOR_PREREQ",
            "Plateforme macOS détectée : tor-browser-selenium n’est pas officiellement supporté",
            platform=platform,
        )
    else:
        log_event(
            "TOR_PREREQ",
            "Plateforme potentiellement non supportée pour tor-browser-selenium",
            platform=platform,
        )

    driver_path = shutil.which("geckodriver")
    if driver_path:
        log_event("TOR_PREREQ", "geckodriver détecté", path=driver_path)
    else:
        log_event(
            "TOR_PREREQ",
            "geckodriver introuvable",
            advice="Installez geckodriver 0.31.0 et ajoutez-le à PATH",
        )

    if cm is None or launch_tbb_tor_with_stem is None:
        log_event("TOR_PREREQ", "Bibliothèque tor-browser-selenium indisponible")
    else:
        log_event("TOR_PREREQ", "Bibliothèque tor-browser-selenium disponible")


def _log_daemon_guidance() -> None:
    global _tor_guidance_logged
    if _tor_guidance_logged:
        return

    _tor_guidance_logged = True
    log_event(
        "TOR_GUIDE",
        "Préférez le service Tor local avec proxy SOCKS sur cette plateforme",
        steps=[
            "brew install tor",  # guidance for macOS users
            "brew install geckodriver",
            "Configurer SocksPort 9050 et ControlPort 9051 dans torrc",
            "Définir TOR_SOCKS_PROXY=socks5://127.0.0.1:9050 dans keys.py ou l’environnement",
        ],
    )


def ensure_local_tor_proxy(tor_browser_path: Optional[str]) -> Tuple[Optional[str], Optional[TorProcessManager]]:
    """Ensure that a Tor proxy is available, launching Tor Browser if needed."""

    global _tor_manager, _tor_checked

    _report_tor_prerequisites()

    if os.getenv("TOR_SOCKS_PROXY"):
        log_event("TOR_CONFIG", "Proxy Tor défini via l’environnement", proxy=os.getenv("TOR_SOCKS_PROXY"))
        return os.getenv("TOR_SOCKS_PROXY"), None

    if _tor_checked:
        if _tor_manager:
            return _tor_manager.proxy_url, _tor_manager
        return None, None

    _tor_checked = True

    platform = sys.platform
    if not tor_browser_path:
        log_event("TOR_CONFIG", "Aucun chemin Tor Browser fourni")
        if platform != "linux" and not platform.startswith("linux"):
            _log_daemon_guidance()
        return None, None

    if platform != "linux" and not platform.startswith("linux"):
        _log_daemon_guidance()
        log_event(
            "TOR_CONFIG",
            "Démarrage automatique de Tor Browser ignoré",
            reason="unsupported-platform",
            platform=platform,
        )
        return None, None

    browser_path = Path(tor_browser_path).expanduser()
    browser_folder = browser_path / "Browser"
    if browser_folder.exists():
        log_event("TOR_PREREQ", "Dossier Tor Browser valide détecté", path=str(browser_path))
    else:
        log_event(
            "TOR_PREREQ",
            "Le chemin Tor Browser ne contient pas de dossier ‘Browser’",
            path=str(browser_path),
        )

    manager = TorProcessManager(browser_path)
    proxy = manager.start()
    if proxy:
        _tor_manager = manager
        os.environ.setdefault("TOR_SOCKS_PROXY", proxy)
        log_event("TOR_CONFIG", "Proxy Tor démarré automatiquement", proxy=proxy)
        return proxy, manager

    log_event("TOR_CONFIG", "Impossible de démarrer un proxy Tor local")
    return None, None


def request_new_tor_identity(control_port: Optional[int], password: Optional[str] = None) -> bool:
    """Send a NEWNYM signal to Tor if control port access is configured."""

    if control_port is None:
        log_event("TOR_CONTROL", "Aucun port de contrôle Tor configuré")
        return False

    if Controller is None or Signal is None:
        log_event("TOR_CONTROL", "Module stem indisponible pour NEWNYM")
        return False

    try:
        with Controller.from_port(port=control_port) as controller:
            if password:
                controller.authenticate(password=password)
            else:
                controller.authenticate()
            controller.signal(Signal.NEWNYM)
    except Exception as exc:  # pragma: no cover - depends on user environment
        log_exception(
            "TOR_CONTROL",
            "Impossible d’envoyer le signal NEWNYM",
            exc,
            port=control_port,
        )
        return False

    log_event("TOR_CONTROL", "Signal NEWNYM envoyé", port=control_port)
    return True
