"""Helpers: path handling, file detection, output folder naming."""
from __future__ import annotations
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List

SUPPORTED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
SUPPORTED_PDF_EXT = {".pdf"}
ALL_SUPPORTED = SUPPORTED_IMAGE_EXT | SUPPORTED_PDF_EXT


def app_base_dir() -> Path:
    """Directory where the app is running from (works for script and PyInstaller EXE)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def count_files(folder: Path) -> Dict[str, int]:
    """Count files by extension in the given folder (non-recursive)."""
    counts = {"jpg": 0, "jpeg": 0, "png": 0, "pdf": 0, "total": 0}
    if not folder.is_dir():
        return counts
    for p in folder.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext == ".jpg":
            counts["jpg"] += 1
        elif ext == ".jpeg":
            counts["jpeg"] += 1
        elif ext == ".png":
            counts["png"] += 1
        elif ext == ".pdf":
            counts["pdf"] += 1
        else:
            continue
        counts["total"] += 1
    return counts


def list_supported_files(folder: Path) -> List[Path]:
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ALL_SUPPORTED]
    )


def resolve_output_folder(input_folder: Path) -> Path:
    """
    Given .../dtfs-insa produce .../dtfs-insa-saida, then -saida-2, -saida-3, ...
    """
    parent = input_folder.parent
    base = f"{input_folder.name}-saida"
    candidate = parent / base
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        candidate = parent / f"{base}-{i}"
        if not candidate.exists():
            return candidate
        i += 1


_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_stem(name: str) -> str:
    """
    Return an ASCII-safe version of a filename stem.
    Keeps underscores/dots/dashes; replaces anything else with '-'.
    Used to avoid ImageMagick issues with exotic characters.
    """
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    cleaned = _SAFE_RE.sub("-", ascii_only).strip("-._")
    return cleaned or "arquivo"


def unique_path(target: Path) -> Path:
    """If target exists, append -1, -2, ... before extension."""
    if not target.exists():
        return target
    stem, suf, parent = target.stem, target.suffix, target.parent
    i = 1
    while True:
        cand = parent / f"{stem}-{i}{suf}"
        if not cand.exists():
            return cand
        i += 1
