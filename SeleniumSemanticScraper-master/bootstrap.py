"""Runtime helpers to bootstrap a dedicated virtual environment.

The application is designed so that end users only need to run::

    cd SeleniumSemanticScraper-master
    python Main.py

On the first launch, :func:`ensure_environment` creates a virtual
environment inside the project directory, installs/updates the
requirements and restarts the script inside that environment. Subsequent
runs reuse the existing environment and skip the expensive operations.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

from activity_logger import log_event, log_exception

_SENTINEL_ENV = "SEMANTIC_SCRAPER_BOOTSTRAPPED"
_STATE_FILE = ".bootstrap_state.json"


def _run_command(command: Sequence[str]) -> None:
    """Execute *command* and stream its output."""

    display_cmd = " ".join(command)
    print(f"→ {display_cmd}")
    log_event("BOOTSTRAP_COMMAND", "Exécution d’une commande système", command=display_cmd)
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as exc:
        log_exception(
            "BOOTSTRAP_ERROR",
            "La commande système a échoué",
            exc,
            command=display_cmd,
            returncode=exc.returncode,
        )
        raise
    log_event("BOOTSTRAP_COMMAND", "Commande terminée", command=display_cmd)


def _python_executable(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _is_running_inside(venv_dir: Path) -> bool:
    try:
        return Path(sys.executable).resolve().is_relative_to(venv_dir.resolve())
    except AttributeError:  # Python < 3.9 fallback
        try:
            Path(sys.executable).resolve().relative_to(venv_dir.resolve())
            return True
        except ValueError:
            return False


def _fingerprint(root_dir: Path, extra_sources: Iterable[Path]) -> str:
    hasher = hashlib.sha256()
    requirements = root_dir / "requirements.txt"
    if requirements.exists():
        hasher.update(requirements.read_bytes())
    for source in extra_sources:
        hasher.update(str(source.resolve()).encode("utf-8"))
        if source.is_file():
            hasher.update(source.read_bytes())
    hasher.update(sys.version.encode("utf-8"))
    return hasher.hexdigest()


def _state_matches(venv_dir: Path, fingerprint: str) -> bool:
    state_file = venv_dir / _STATE_FILE
    if not state_file.exists():
        return False
    try:
        with state_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (ValueError, OSError):
        return False
    return data.get("fingerprint") == fingerprint


def _update_state(venv_dir: Path, fingerprint: str) -> None:
    state_file = venv_dir / _STATE_FILE
    try:
        with state_file.open("w", encoding="utf-8") as handle:
            json.dump({"fingerprint": fingerprint}, handle)
    except OSError:
        pass


def _create_virtualenv(venv_dir: Path) -> None:
    import venv

    builder = venv.EnvBuilder(with_pip=True)
    builder.create(str(venv_dir))


def _install_requirements(venv_python: Path, root_dir: Path) -> None:
    project_requirements = root_dir / "requirements.txt"
    tor_repo = root_dir.parent / "tor-browser-selenium-main"

    commands: List[List[str]] = [
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
    ]

    if project_requirements.exists():
        commands.append([str(venv_python), "-m", "pip", "install", "--upgrade", "-r", str(project_requirements)])

    # Ensure Stem is always available even if requirements.txt omits it.
    commands.append([str(venv_python), "-m", "pip", "install", "--upgrade", "stem"])

    if tor_repo.exists():
        commands.append([str(venv_python), "-m", "pip", "install", "--upgrade", str(tor_repo)])
    else:
        # Fallback to the PyPI package if the local repository is missing.
        commands.append([str(venv_python), "-m", "pip", "install", "--upgrade", "tbselenium"])

    for command in commands:
        _run_command(command)


def ensure_environment(entrypoint: str) -> None:
    """Guarantee that the program runs from a managed virtual environment."""

    root_dir = Path(entrypoint).resolve().parent
    venv_dir = root_dir / ".venv"
    log_event(
        "BOOTSTRAP_START",
        "Initialisation de l’environnement virtuel",
        root=str(root_dir),
        entrypoint=str(entrypoint),
    )
    if os.environ.get(_SENTINEL_ENV) == "1":
        log_event("BOOTSTRAP_SKIP", "Exécution déjà relancée dans l’environnement virtuel géré")
        return

    if _is_running_inside(venv_dir):
        log_event("BOOTSTRAP_SKIP", "Le script s’exécute déjà depuis l’environnement virtuel", venv=str(venv_dir))
        return

    print("Préparation de l’environnement virtuel local…")
    if not venv_dir.exists():
        print(f"Création du dossier {venv_dir} …")
        _create_virtualenv(venv_dir)
        log_event("BOOTSTRAP_VENV", "Création de l’environnement virtuel", venv=str(venv_dir))
    else:
        log_event("BOOTSTRAP_VENV", "Réutilisation de l’environnement virtuel existant", venv=str(venv_dir))

    venv_python = _python_executable(venv_dir)
    fingerprint = _fingerprint(root_dir, [root_dir / "requirements.txt", root_dir.parent / "tor-browser-selenium-main"])
    if not _state_matches(venv_dir, fingerprint):
        print("Installation et mise à jour des dépendances…")
        _install_requirements(venv_python, root_dir)
        _update_state(venv_dir, fingerprint)
        log_event(
            "BOOTSTRAP_DEPENDENCIES",
            "Dépendances installées/mises à jour",
            venv_python=str(venv_python),
        )
    else:
        print("Environnement virtuel déjà à jour.")
        log_event(
            "BOOTSTRAP_DEPENDENCIES",
            "Aucune mise à jour nécessaire : empreinte identique",
            venv_python=str(venv_python),
        )

    env = os.environ.copy()
    env[_SENTINEL_ENV] = "1"
    entrypoint_path = Path(entrypoint).resolve()
    args = [str(venv_python), str(entrypoint_path), *sys.argv[1:]]
    log_event(
        "BOOTSTRAP_EXEC",
        "Relance du script dans l’environnement virtuel",
        python=str(venv_python),
        args=args,
    )
    os.execve(str(venv_python), args, env)
