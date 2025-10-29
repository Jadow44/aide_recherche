"""Utilities for preparing persistent storage directories for search results.

This module centralizes the sanitization logic used before writing files so the
same rules apply when different components (crawler, exporter, downloader)
access the results folders. It also logs adjustments to help diagnose
filesystem-related issues reported by users.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

from activity_logger import log_event, log_exception

_INVALID_CHARS = re.compile(r"[\\/:*?\"<>|]")
_MULTISPACE = re.compile(r"\s+")


def sanitize_search_label(label: str) -> str:
    """Return a filesystem-friendly label based on *label*.

    The sanitization keeps human-readable spaces but collapses consecutive
    whitespace, trims leading/trailing blanks, removes characters that are not
    supported on Windows filesystems, and strips trailing dots that can cause
    issues on some platforms. An empty input falls back to ``"Recherche"``.
    """

    cleaned = _MULTISPACE.sub(" ", (label or "").strip())
    cleaned = _INVALID_CHARS.sub("_", cleaned)
    cleaned = cleaned.rstrip(" .")
    return cleaned or "Recherche"


def _maybe_migrate_directory(original: Path, sanitized: Path) -> None:
    if not original.exists() or original == sanitized:
        return

    if sanitized.exists():
        log_event(
            "STORAGE_MIGRATE",
            "Ancien dossier détecté mais le répertoire cible existe déjà",
            original=str(original),
            target=str(sanitized),
        )
        return

    try:
        original.rename(sanitized)
    except OSError as exc:
        log_exception(
            "STORAGE_MIGRATE_ERROR",
            "Impossible de renommer l’ancien dossier de résultats",
            exc,
            original=str(original),
            target=str(sanitized),
        )
    else:
        log_event(
            "STORAGE_MIGRATE",
            "Ancien dossier renommé pour supprimer les caractères problématiques",
            original=str(original),
            target=str(sanitized),
        )


def prepare_results_directory(root_directory: os.PathLike[str] | str, label: str) -> Tuple[str, Path]:
    """Ensure the results directory for *label* exists and return its path.

    Returns a tuple ``(sanitized_label, directory_path)`` where
    ``sanitized_label`` is the cleaned version produced by
    :func:`sanitize_search_label` and ``directory_path`` is the corresponding
    folder inside ``<root_directory>/Results``.
    """

    root_path = Path(root_directory)
    results_root = root_path / "Results"
    results_root.mkdir(parents=True, exist_ok=True)

    sanitized_label = sanitize_search_label(label)
    if sanitized_label != label:
        log_event(
            "STORAGE_SANITIZE",
            "Libellé de recherche nettoyé pour le stockage",
            original=label,
            sanitized=sanitized_label,
        )

    target_dir = results_root / sanitized_label
    legacy_dir = results_root / label
    _maybe_migrate_directory(legacy_dir, target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    log_event(
        "STORAGE_DIRECTORY",
        "Répertoire de résultats prêt",
        label=sanitized_label,
        path=str(target_dir),
    )
    return sanitized_label, target_dir


def resolve_storage_paths(root_directory: os.PathLike[str] | str, label: str) -> Tuple[str, Path, Path, Path]:
    """Return convenient paths for the pickle files associated with *label*."""

    sanitized_label, directory = prepare_results_directory(root_directory, label)
    authors_path = directory / "Authors.pkl"
    articles_path = directory / "Articles.pkl"
    return sanitized_label, directory, authors_path, articles_path


__all__ = [
    "sanitize_search_label",
    "prepare_results_directory",
    "resolve_storage_paths",
]
