"""Core batch processing logic. Runs in a worker thread."""
from __future__ import annotations
import io
import shutil
import tempfile
import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import fitz  # PyMuPDF
from PIL import Image

from .magick import MagickError, find_magick, run_magick
from .utils import (
    ALL_SUPPORTED,
    SUPPORTED_IMAGE_EXT,
    SUPPORTED_PDF_EXT,
    count_files,
    list_supported_files,
    safe_stem,
    unique_path,
)


# ---- Settings dataclasses -------------------------------------------------

@dataclass
class CartoonSettings:
    # Note: floodfill is ALWAYS applied (matching original .bat behavior).
    # `remove_background_near_white` only controls whether fuzz is used (5%) or not (0%).
    remove_background_near_white: bool = True   # True -> fuzz 5%, False -> fuzz 0%
    swap_absolute_white: bool = True            # 255,255,255 -> 252,252,252


@dataclass
class RemoveBgSettings:
    """Modo dedicado: remove fundo sólido (branco ou preto) e troca branco 255->252."""
    background_color: str = "black"             # "white" | "black" -> cor do fundo a remover
    remove_near: bool = True                    # True -> fuzz 5%, False -> fuzz 0%
    swap_absolute_white: bool = True            # 255,255,255 -> 252,252,252


@dataclass
class ScannedSettings:
    fuzz_level: int = 2          # 1=0%, 2=8%, 3=15%, 4=22%
    extra_cleanup: bool = True
    reinforce_strokes: bool = True
    reinforce_level: int = 2     # 1=6%, 2=10%, 3=15%


@dataclass
class DirtyPaperSettings:
    fuzz_level: int = 1          # 1=18%, 2=22%, 3=28%
    reinforce_level: int = 2     # 1=6%, 2=10%, 3=15%


@dataclass
class ProcessJob:
    input_folder: Path
    output_folder: Path
    mode: str                     # "cartoon" | "scanned" | "dirty" | "removebg"
    pdf_dpi: int = 300
    cartoon: CartoonSettings = field(default_factory=CartoonSettings)
    scanned: ScannedSettings = field(default_factory=ScannedSettings)
    dirty: DirtyPaperSettings = field(default_factory=DirtyPaperSettings)
    removebg: RemoveBgSettings = field(default_factory=RemoveBgSettings)


@dataclass
class ProcessReport:
    counts_in: Dict[str, int] = field(default_factory=dict)
    png_generated: int = 0
    errors: int = 0
    output_folder: Optional[Path] = None
    error_details: List[str] = field(default_factory=list)


# ---- Mapping helpers ------------------------------------------------------

_SCANNED_FUZZ = {1: 0, 2: 8, 3: 15, 4: 22}
_DIRTY_FUZZ = {1: 18, 2: 22, 3: 28}
_LEVEL_PCT = {1: 6, 2: 10, 3: 15}


def _build_mogrify_args_cartoon(s: CartoonSettings) -> List[str]:
    """
    Mirrors original .bat exactly. Floodfill is ALWAYS applied; fuzz is 5% when
    "remove background near white" is on, 0% when off.
    """
    fuzz = "5%" if s.remove_background_near_white else "0%"
    args: List[str] = [
        "-fuzz", fuzz,
        "-alpha", "set",
        "-channel", "rgba",
        "-fill", "none",
        "-floodfill", "+0+0", "white",
    ]
    if s.swap_absolute_white:
        args += [
            "-channel", "rgba",
            "-fill", "rgb(252,252,252)",
            "-opaque", "rgb(255,255,255)",
        ]
    return args


def _build_mogrify_args_removebg(s: RemoveBgSettings) -> List[str]:
    """
    Modo dedicado de remoção de fundo sólido. Diferente do Cartoon (que usa
    floodfill a partir do canto), aqui removemos a cor do fundo na imagem
    INTEIRA via -transparent, então o preto/branco preso dentro das letras
    também some e não fica a "linha" da fronteira do floodfill.

    Opcionalmente troca branco puro 255 -> 252.
    """
    fuzz = "15%" if s.remove_near else "0%"
    bg = "black" if s.background_color == "black" else "white"
    args: List[str] = [
        "-alpha", "set",
        "-fuzz", fuzz,
        "-transparent", bg,
    ]
    if s.swap_absolute_white:
        # fuzz de volta a 0 para trocar APENAS o branco puro 255,255,255 por 252.
        args += [
            "-fuzz", "0%",
            "-channel", "rgba",
            "-fill", "rgb(252,252,252)",
            "-opaque", "rgb(255,255,255)",
        ]
    return args


def _build_mogrify_args_scanned(s: ScannedSettings) -> List[str]:
    """
    Mirrors .bat:
      [level] -alpha set -fuzz F% -transparent white
      [ -channel A -threshold 10% -morphology Open Diamond:1 +channel ]
    """
    args: List[str] = []
    if s.reinforce_strokes:
        pct = _LEVEL_PCT[s.reinforce_level]
        args += ["-level", f"{pct}%,100%"]
    args += ["-alpha", "set", "-fuzz", f"{_SCANNED_FUZZ[s.fuzz_level]}%", "-transparent", "white"]
    if s.extra_cleanup:
        args += ["-channel", "A", "-threshold", "10%", "-morphology", "Open", "Diamond:1", "+channel"]
    return args


def _build_mogrify_args_dirty(s: DirtyPaperSettings) -> List[str]:
    """Dirty paper: cleanup always on, reinforce always on, threshold 12%."""
    pct = _LEVEL_PCT[s.reinforce_level]
    return [
        "-level", f"{pct}%,100%",
        "-alpha", "set",
        "-fuzz", f"{_DIRTY_FUZZ[s.fuzz_level]}%",
        "-transparent", "white",
        "-channel", "A",
        "-threshold", "12%",
        "-morphology", "Open", "Diamond:1",
        "+channel",
    ]


def build_ops(job: ProcessJob) -> List[str]:
    if job.mode == "cartoon":
        return _build_mogrify_args_cartoon(job.cartoon)
    if job.mode == "scanned":
        return _build_mogrify_args_scanned(job.scanned)
    if job.mode == "dirty":
        return _build_mogrify_args_dirty(job.dirty)
    if job.mode == "removebg":
        return _build_mogrify_args_removebg(job.removebg)
    raise ValueError(f"Modo desconhecido: {job.mode}")


# ---- PDF rasterization ----------------------------------------------------

def rasterize_pdf(pdf_path: Path, out_dir: Path, dpi: int, log) -> List[Path]:
    """Rasterize each page of a PDF to PNG using PyMuPDF. Returns list of PNG paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    produced: List[Path] = []
    stem = safe_stem(pdf_path.stem)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out = out_dir / f"{stem}-pagina-{i:03d}.png"
            # MuPDF anti-aliases the page boundary, leaving a 1px gray frame on the
            # bottom/right edges. That gray is neither black nor white, so no mode's
            # background removal catches it and it shows up as a thin line exactly at
            # the canvas edge. Shave a 1px border to drop it before processing.
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            w, h = img.size
            if w > 2 and h > 2:
                img = img.crop((1, 1, w - 1, h - 1))
            img.save(out)
            produced.append(out)
            log(f"   PDF {pdf_path.name} · pág {i+1}/{len(doc)} → {out.name}")
    return produced


# ---- Orchestrator ---------------------------------------------------------

class Processor:
    def __init__(
        self,
        log: Callable[[str], None],
        progress: Callable[[int, int], None],
        stage: Callable[[str], None],
    ):
        self.log = log
        self.progress = progress
        self.stage = stage
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise RuntimeError("Processamento cancelado pelo usuário.")

    def run(self, job: ProcessJob) -> ProcessReport:
        report = ProcessReport(output_folder=job.output_folder)
        report.counts_in = count_files(job.input_folder)

        if report.counts_in["total"] == 0:
            raise RuntimeError("Nenhum arquivo suportado encontrado na pasta.")

        magick_exe = find_magick()
        if not magick_exe:
            raise RuntimeError(
                "ImageMagick não foi encontrado. Instale em "
                "https://imagemagick.org/script/download.php#windows "
                "ou coloque a versão portable em vendor/ImageMagick/ ao lado do executável."
            )
        self.log(f"ImageMagick: {magick_exe}")

        job.output_folder.mkdir(parents=True, exist_ok=True)
        self.log(f"Pasta de saída: {job.output_folder}")

        ops = build_ops(job)

        tmp_root = Path(tempfile.mkdtemp(prefix="dtf_pdf_"))
        self.log(f"Temporário: {tmp_root}")

        try:
            files = list_supported_files(job.input_folder)

            # 1) Convert PDFs first
            pdfs = [p for p in files if p.suffix.lower() in SUPPORTED_PDF_EXT]
            images = [p for p in files if p.suffix.lower() in SUPPORTED_IMAGE_EXT]

            rasterized: List[Path] = []
            if pdfs:
                self.stage("Convertendo PDFs...")
                for idx, pdf in enumerate(pdfs, 1):
                    self._check_cancel()
                    self.log(f"[PDF {idx}/{len(pdfs)}] {pdf.name}")
                    try:
                        rasterized.extend(rasterize_pdf(pdf, tmp_root, job.pdf_dpi, self.log))
                    except Exception as e:
                        report.errors += 1
                        msg = f"Erro convertendo {pdf.name}: {e}"
                        report.error_details.append(msg)
                        self.log("  ✗ " + msg)

            # 2) Process all images (originals + rasterized PDF pages)
            all_inputs = images + rasterized
            total = len(all_inputs)
            self.stage("Processando imagens...")
            self.progress(0, total)

            for i, src in enumerate(all_inputs, 1):
                self._check_cancel()
                dst = unique_path(job.output_folder / (safe_stem(src.stem) + ".png"))
                try:
                    run_magick(magick_exe, [str(src), *ops, str(dst)])
                    report.png_generated += 1
                    self.log(f"[{i}/{total}] ✓ {src.name} → {dst.name}")
                except MagickError as e:
                    report.errors += 1
                    msg = f"Erro processando {src.name}: {e}"
                    report.error_details.append(msg)
                    self.log(f"[{i}/{total}] ✗ {msg}")
                except Exception as e:
                    report.errors += 1
                    msg = f"Erro inesperado em {src.name}: {e}\n{traceback.format_exc()}"
                    report.error_details.append(msg)
                    self.log(f"[{i}/{total}] ✗ {msg}")
                self.progress(i, total)

            self.stage("Limpando temporários...")
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

        self.stage("Concluído")
        return report
