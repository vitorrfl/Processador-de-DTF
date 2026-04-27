"""ImageMagick detection and subprocess wrapper."""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .utils import app_base_dir


def _no_window_flags() -> int:
    """Prevent a console window from popping up on Windows."""
    if os.name == "nt":
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return 0


def find_magick() -> Optional[str]:
    """
    Locate ImageMagick's 'magick' executable.
    Search order:
      1. Bundled vendor/ImageMagick/magick.exe (portable ship-with-app)
      2. PATH
      3. Default install path C:\\Program Files\\ImageMagick-*\\magick.exe
    """
    vendored = app_base_dir() / "vendor" / "ImageMagick" / "magick.exe"
    if vendored.is_file():
        return str(vendored)

    in_path = shutil.which("magick")
    if in_path:
        return in_path

    if os.name == "nt":
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        if pf.is_dir():
            for sub in sorted(pf.glob("ImageMagick-*"), reverse=True):
                exe = sub / "magick.exe"
                if exe.is_file():
                    return str(exe)
    return None


class MagickError(RuntimeError):
    pass


def run_magick(magick_exe: str, args: List[str], timeout: int = 300) -> None:
    """Run `magick <args>` and raise on non-zero exit."""
    cmd = [magick_exe] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_no_window_flags(),
        )
    except FileNotFoundError as e:
        raise MagickError(f"ImageMagick não encontrado: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise MagickError(f"Timeout executando ImageMagick: {e}") from e

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise MagickError(f"ImageMagick falhou ({proc.returncode}): {err}")
