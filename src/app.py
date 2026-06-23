"""CustomTkinter UI for the DTF Processor."""
from __future__ import annotations
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image

from .processor import (
    CartoonSettings,
    DirtyPaperSettings,
    ProcessJob,
    ProcessReport,
    Processor,
    RemoveBgSettings,
    ScannedSettings,
)
from .utils import count_files, resolve_output_folder

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT = "#3A86FF"
ACCENT_HOVER = "#2F6FD8"
CARD_BG = "#1E1E24"
CARD_BORDER = "#2A2A32"


class Card(ctk.CTkFrame):
    def __init__(self, master, title: str, **kw):
        super().__init__(master, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=12, **kw)
        self.grid_columnconfigure(0, weight=1)
        self._title = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=14, weight="bold"))
        self._title.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.body.grid_columnconfigure(0, weight=1)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Processador de DTFs")
        self.geometry("1100x760")
        self.minsize(980, 700)
        self._apply_window_icon()

        self._queue: queue.Queue = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._processor: Optional[Processor] = None
        self._last_output: Optional[Path] = None

        self._build_ui()
        self.after(80, self._drain_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)

    # ---- Assets ---------------------------------------------------------

    def _assets_dir(self) -> Path:
        """Locate assets/ both in dev and inside the PyInstaller bundle."""
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        else:
            base = Path(__file__).resolve().parent.parent
        return base / "assets"

    def _apply_window_icon(self):
        # Use the default tkinter icon for title bar / taskbar (cleaner at small sizes).
        # The Tecnosup logo stays on the .exe, installer, shortcut and inside the app header.

        # Close PyInstaller splash screen if running as built exe
        try:
            import pyi_splash  # type: ignore
            pyi_splash.close()
        except Exception:
            pass

    # ---- UI -------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(18, 8))

        logo_path = self._assets_dir() / "logo.png"
        if logo_path.exists():
            try:
                pil = Image.open(logo_path)
                ratio = pil.width / pil.height
                logo_h = 56
                logo_w = int(logo_h * ratio)
                logo_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(logo_w, logo_h))
                ctk.CTkLabel(header, image=logo_img, text="").pack(side="left")
            except Exception:
                ctk.CTkLabel(header, text="Processador de DTFs", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        else:
            ctk.CTkLabel(header, text="Processador de DTFs", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")

        ctk.CTkLabel(header, text="   Processador de DTFs", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text="   ·  Desenvolvido por Tecnosup", text_color="#9AA0A6").pack(side="left")

        # --- Folder & counts card ---
        folder_card = Card(self, "1. Pasta de entrada")
        folder_card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=8)
        folder_card.body.grid_columnconfigure(0, weight=1)

        self.path_var = ctk.StringVar()
        path_row = ctk.CTkFrame(folder_card.body, fg_color="transparent")
        path_row.grid(row=0, column=0, sticky="ew")
        path_row.grid_columnconfigure(0, weight=1)
        self.path_entry = ctk.CTkEntry(path_row, textvariable=self.path_var, height=38, placeholder_text="Cole ou selecione uma pasta…")
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.path_entry.bind("<KeyRelease>", lambda e: self._refresh_counts())
        ctk.CTkButton(path_row, text="Selecionar pasta", height=38, corner_radius=10,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._pick_folder).grid(row=0, column=1)

        self.counts_label = ctk.CTkLabel(folder_card.body, text="—", text_color="#9AA0A6", anchor="w", justify="left")
        self.counts_label.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        # --- Mode card (left) ---
        mode_card = Card(self, "2. Modo de processamento")
        mode_card.grid(row=2, column=0, sticky="nsew", padx=(20, 10), pady=8)
        self._build_mode_card(mode_card)

        # --- Progress & log card (right) ---
        right_card = Card(self, "3. Progresso")
        right_card.grid(row=2, column=1, sticky="nsew", padx=(10, 20), pady=8)
        self._build_progress_card(right_card)

        # --- Bottom action bar ---
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 18))
        actions.grid_columnconfigure(3, weight=1)

        self.start_btn = ctk.CTkButton(actions, text="Iniciar processamento", height=44, corner_radius=12,
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                       command=self._start)
        self.start_btn.grid(row=0, column=0, padx=(0, 8))

        self.open_btn = ctk.CTkButton(actions, text="Abrir pasta de saída", height=44, corner_radius=12,
                                      fg_color="#2A2A32", hover_color="#33333D",
                                      command=self._open_output, state="disabled")
        self.open_btn.grid(row=0, column=1, padx=8)

        self.reset_btn = ctk.CTkButton(actions, text="Processar outra pasta", height=44, corner_radius=12,
                                       fg_color="#2A2A32", hover_color="#33333D",
                                       command=self._reset)
        self.reset_btn.grid(row=0, column=2, padx=8)

        ctk.CTkButton(actions, text="Sair", height=44, width=100, corner_radius=12,
                      fg_color="#3A1F22", hover_color="#4A2A2E",
                      command=self._on_close_request).grid(row=0, column=4, padx=(8, 0))

    def _build_mode_card(self, card: Card):
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.mode_var = ctk.StringVar(value="cartoon")
        seg = ctk.CTkSegmentedButton(
            body,
            values=["Cartoon / IA", "Escaneado", "Papel sujo", "Remover fundo"],
            command=self._on_mode_change,
        )
        seg.set("Cartoon / IA")
        seg.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._seg = seg

        self._mode_area = ctk.CTkFrame(body, fg_color="transparent")
        self._mode_area.grid(row=1, column=0, sticky="nsew")
        self._mode_area.grid_columnconfigure(0, weight=1)

        # Cartoon frame
        self._cartoon_f = ctk.CTkFrame(self._mode_area, fg_color="transparent")
        self._cartoon_f.grid_columnconfigure(0, weight=1)
        self.cartoon_remove_bg = ctk.CTkSwitch(self._cartoon_f, text="Remover tons próximos do branco no fundo (fuzz 5%)")
        self.cartoon_remove_bg.select()
        self.cartoon_remove_bg.grid(row=0, column=0, sticky="w", pady=4)
        ctk.CTkLabel(self._cartoon_f,
                     text="Desligado: floodfill ainda é aplicado, mas só remove branco puro (fuzz 0%).",
                     text_color="#9AA0A6", justify="left", wraplength=400).grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.cartoon_swap_white = ctk.CTkSwitch(self._cartoon_f, text="Trocar branco absoluto (255) por 252")
        self.cartoon_swap_white.select()
        self.cartoon_swap_white.grid(row=2, column=0, sticky="w", pady=4)

        # Remove background frame (modo dedicado)
        self._removebg_f = ctk.CTkFrame(self._mode_area, fg_color="transparent")
        self._removebg_f.grid_columnconfigure(0, weight=1)
        rbg_row = ctk.CTkFrame(self._removebg_f, fg_color="transparent")
        rbg_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        rbg_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rbg_row, text="Cor do fundo a remover:").grid(row=0, column=0, sticky="w")
        self.removebg_color = ctk.CTkOptionMenu(rbg_row, values=["Preto (letra branca)", "Branco (letra escura)"])
        self.removebg_color.set("Preto (letra branca)")
        self.removebg_color.grid(row=0, column=1, sticky="e")
        self.removebg_near = ctk.CTkSwitch(self._removebg_f, text="Remover tons próximos da cor do fundo (fuzz 5%)")
        self.removebg_near.select()
        self.removebg_near.grid(row=1, column=0, sticky="w", pady=4)
        ctk.CTkLabel(self._removebg_f,
                     text="Desligado: remove só a cor pura do fundo (fuzz 0%).",
                     text_color="#9AA0A6", justify="left", wraplength=400).grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.removebg_swap_white = ctk.CTkSwitch(self._removebg_f, text="Trocar branco absoluto (255) por 252")
        self.removebg_swap_white.select()
        self.removebg_swap_white.grid(row=3, column=0, sticky="w", pady=4)

        # Scanned frame
        self._scanned_f = ctk.CTkFrame(self._mode_area, fg_color="transparent")
        self._scanned_f.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._scanned_f, text="Nível para remover branco do papel:").grid(row=0, column=0, sticky="w", pady=(6, 2))
        self.scanned_fuzz = ctk.CTkOptionMenu(self._scanned_f, values=[
            "1. Só branco absoluto (0%)", "2. Leve (8%)", "3. Médio (15%)", "4. Forte (22%)"])
        self.scanned_fuzz.set("3. Médio (15%)")
        self.scanned_fuzz.grid(row=1, column=0, sticky="ew", pady=2)
        self.scanned_cleanup = ctk.CTkSwitch(self._scanned_f, text="Limpeza extra (pontinhos/halos brancos)")
        self.scanned_cleanup.select()
        self.scanned_cleanup.grid(row=2, column=0, sticky="w", pady=(10, 4))
        self.scanned_reinforce = ctk.CTkSwitch(self._scanned_f, text="Reforçar traços de canetinha",
                                               command=self._toggle_reinforce)
        self.scanned_reinforce.select()
        self.scanned_reinforce.grid(row=3, column=0, sticky="w", pady=4)
        ctk.CTkLabel(self._scanned_f, text="Intensidade do reforço:").grid(row=4, column=0, sticky="w", pady=(6, 2))
        self.scanned_level = ctk.CTkOptionMenu(self._scanned_f, values=[
            "1. Leve (6%)", "2. Média (10%)", "3. Forte (15%)"])
        self.scanned_level.set("2. Média (10%)")
        self.scanned_level.grid(row=5, column=0, sticky="ew", pady=2)

        # Dirty frame
        self._dirty_f = ctk.CTkFrame(self._mode_area, fg_color="transparent")
        self._dirty_f.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._dirty_f, text="Força para remover sujeira do papel:").grid(row=0, column=0, sticky="w", pady=(6, 2))
        self.dirty_fuzz = ctk.CTkOptionMenu(self._dirty_f, values=[
            "1. Médio/Forte (18%)", "2. Forte (22%)", "3. Muito forte (28%)"])
        self.dirty_fuzz.set("1. Médio/Forte (18%)")
        self.dirty_fuzz.grid(row=1, column=0, sticky="ew", pady=2)
        ctk.CTkLabel(self._dirty_f, text="Reforço de traços:").grid(row=2, column=0, sticky="w", pady=(10, 2))
        self.dirty_level = ctk.CTkOptionMenu(self._dirty_f, values=[
            "1. Leve (6%)", "2. Médio (10%)", "3. Forte (15%)"])
        self.dirty_level.set("2. Médio (10%)")
        self.dirty_level.grid(row=3, column=0, sticky="ew", pady=2)
        ctk.CTkLabel(self._dirty_f,
                     text="Neste modo a limpeza extra e o reforço estão sempre ativos\n(threshold alpha 12%).",
                     text_color="#9AA0A6", justify="left").grid(row=4, column=0, sticky="w", pady=(10, 0))

        # PDF DPI at bottom of mode card
        pdf_frame = ctk.CTkFrame(body, fg_color="transparent")
        pdf_frame.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        pdf_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(pdf_frame, text="DPI para PDF:").grid(row=0, column=0, sticky="w")
        self.pdf_dpi = ctk.CTkOptionMenu(pdf_frame, values=["200 DPI (leve)", "300 DPI (recomendado)", "600 DPI (alta qualidade)"])
        self.pdf_dpi.set("300 DPI (recomendado)")
        self.pdf_dpi.grid(row=0, column=1, sticky="e")

        self._show_mode("cartoon")

    def _build_progress_card(self, card: Card):
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        self.stage_label = ctk.CTkLabel(body, text="Aguardando...", anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        self.stage_label.grid(row=0, column=0, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(body, height=14, corner_radius=7, progress_color=ACCENT)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(8, 12))

        self.log_box = ctk.CTkTextbox(body, fg_color="#121216", border_color=CARD_BORDER, border_width=1, corner_radius=10,
                                      font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.grid(row=2, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    # ---- Mode helpers ---------------------------------------------------

    def _on_mode_change(self, value: str):
        mapping = {"Cartoon / IA": "cartoon", "Escaneado": "scanned",
                   "Papel sujo": "dirty", "Remover fundo": "removebg"}
        self._show_mode(mapping[value])

    def _show_mode(self, mode: str):
        for f in (self._cartoon_f, self._scanned_f, self._dirty_f, self._removebg_f):
            f.grid_forget()
        self.mode_var.set(mode)
        if mode == "cartoon":
            self._cartoon_f.grid(row=0, column=0, sticky="nsew")
        elif mode == "scanned":
            self._scanned_f.grid(row=0, column=0, sticky="nsew")
        elif mode == "dirty":
            self._dirty_f.grid(row=0, column=0, sticky="nsew")
        else:
            self._removebg_f.grid(row=0, column=0, sticky="nsew")

    def _toggle_reinforce(self):
        state = "normal" if self.scanned_reinforce.get() else "disabled"
        self.scanned_level.configure(state=state)

    # ---- Folder handling ------------------------------------------------

    def _pick_folder(self):
        current = self.path_var.get().strip()
        initial = current if current and Path(current).is_dir() else None
        folder = filedialog.askdirectory(initialdir=initial)
        if folder:
            self.path_var.set(folder)
            self._refresh_counts()

    def _refresh_counts(self):
        raw = self.path_var.get().strip().strip('"')
        p = Path(raw) if raw else None
        if not p or not p.is_dir():
            self.counts_label.configure(text="—", text_color="#9AA0A6")
            return
        c = count_files(p)
        self.counts_label.configure(
            text=f"JPG: {c['jpg']}   JPEG: {c['jpeg']}   PNG: {c['png']}   PDF: {c['pdf']}   TOTAL: {c['total']}",
            text_color="#E6E6E6" if c["total"] else "#D08A8A",
        )

    # ---- Build job ------------------------------------------------------

    def _current_job(self) -> Optional[ProcessJob]:
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Pasta", "Selecione ou cole o caminho de uma pasta.")
            return None
        inp = Path(raw)
        if not inp.is_dir():
            messagebox.showerror("Pasta inválida", f"A pasta não existe:\n{inp}")
            return None

        out = resolve_output_folder(inp)

        dpi_map = {"200 DPI (leve)": 200, "300 DPI (recomendado)": 300, "600 DPI (alta qualidade)": 600}
        dpi = dpi_map[self.pdf_dpi.get()]

        mode = self.mode_var.get()
        job = ProcessJob(input_folder=inp, output_folder=out, mode=mode, pdf_dpi=dpi)

        if mode == "cartoon":
            bg_color = "black" if self.cartoon_bg_color.get().startswith("Preto") else "white"
            job.cartoon = CartoonSettings(
                remove_background_near_white=bool(self.cartoon_remove_bg.get()),
                swap_absolute_white=bool(self.cartoon_swap_white.get()),
                background_color=bg_color,
            )
        elif mode == "scanned":
            job.scanned = ScannedSettings(
                fuzz_level=int(self.scanned_fuzz.get()[0]),
                extra_cleanup=bool(self.scanned_cleanup.get()),
                reinforce_strokes=bool(self.scanned_reinforce.get()),
                reinforce_level=int(self.scanned_level.get()[0]),
            )
        elif mode == "dirty":
            job.dirty = DirtyPaperSettings(
                fuzz_level=int(self.dirty_fuzz.get()[0]),
                reinforce_level=int(self.dirty_level.get()[0]),
            )
        else:
            bg_color = "black" if self.removebg_color.get().startswith("Preto") else "white"
            job.removebg = RemoveBgSettings(
                background_color=bg_color,
                remove_near=bool(self.removebg_near.get()),
                swap_absolute_white=bool(self.removebg_swap_white.get()),
            )
        return job

    # ---- Run ------------------------------------------------------------

    def _set_busy(self, busy: bool):
        state = "disabled" if busy else "normal"
        self.start_btn.configure(state=state)
        self.path_entry.configure(state=state)

    def _start(self):
        if self._worker and self._worker.is_alive():
            return
        job = self._current_job()
        if not job:
            return

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.progress_bar.set(0)
        self.stage_label.configure(text="Iniciando...")
        self.open_btn.configure(state="disabled")
        self._set_busy(True)
        self._last_output = job.output_folder

        self._processor = Processor(
            log=lambda m: self._queue.put(("log", m)),
            progress=lambda c, t: self._queue.put(("prog", (c, t))),
            stage=lambda s: self._queue.put(("stage", s)),
        )

        def target():
            try:
                report = self._processor.run(job)
                self._queue.put(("done", report))
            except Exception as e:
                self._queue.put(("error", str(e)))

        self._worker = threading.Thread(target=target, daemon=True)
        self._worker.start()

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "prog":
                    cur, total = payload
                    self.progress_bar.set(cur / total if total else 0)
                elif kind == "stage":
                    self.stage_label.configure(text=payload)
                elif kind == "done":
                    self._on_done(payload)
                elif kind == "error":
                    self._on_error(payload)
        except queue.Empty:
            pass
        self.after(80, self._drain_queue)

    def _append_log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_done(self, report: ProcessReport):
        self._set_busy(False)
        self.progress_bar.set(1)
        self.open_btn.configure(state="normal")
        c = report.counts_in
        summary = (
            "\n=============================\n"
            "RELATÓRIO FINAL\n"
            "=============================\n"
            f"JPG encontrados : {c.get('jpg', 0)}\n"
            f"JPEG encontrados: {c.get('jpeg', 0)}\n"
            f"PNG encontrados : {c.get('png', 0)}\n"
            f"PDF encontrados : {c.get('pdf', 0)}\n"
            f"PNGs gerados    : {report.png_generated}\n"
            f"Erros           : {report.errors}\n"
            f"Pasta de saída  : {report.output_folder}\n"
        )
        self._append_log(summary)
        if report.errors:
            self._append_log("Detalhes dos erros:")
            for line in report.error_details:
                self._append_log("  - " + line.splitlines()[0])

    def _on_error(self, msg: str):
        self._set_busy(False)
        self.stage_label.configure(text="Erro")
        self._append_log(f"\n✗ {msg}")
        messagebox.showerror("Erro", msg)

    # ---- Post-run actions ----------------------------------------------

    def _open_output(self):
        if not self._last_output or not self._last_output.exists():
            return
        try:
            if os.name == "nt":
                os.startfile(str(self._last_output))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._last_output)])
            else:
                subprocess.Popen(["xdg-open", str(self._last_output)])
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta:\n{e}")

    # ---- Exit -----------------------------------------------------------

    def _on_close_request(self):
        if self._worker and self._worker.is_alive():
            if not messagebox.askyesno(
                "Processamento em andamento",
                "Há um processamento em andamento. Sair agora vai cancelar.\n\nDeseja sair mesmo assim?",
            ):
                return
            if self._processor:
                self._processor.cancel()
        else:
            if not messagebox.askyesno("Sair", "Deseja realmente sair do Processador de DTFs?"):
                return
        self._show_goodbye_and_close()

    def _show_goodbye_and_close(self):
        try:
            for w in self.winfo_children():
                w.grid_forget()
                w.pack_forget()
        except Exception:
            pass

        # Reset the main-window grid: the build layout left row 2 and column 1 with
        # weight=1, which would split the vertical/horizontal space and push the
        # goodbye frame into the upper-left quadrant instead of centering it.
        for r in range(0, 4):
            self.grid_rowconfigure(r, weight=0)
        for c in range(0, 2):
            self.grid_columnconfigure(c, weight=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bye = ctk.CTkFrame(self, fg_color="transparent")
        bye.grid(row=0, column=0, columnspan=2, sticky="nsew")
        # Top (0) and bottom (4) spacer rows take the slack so the content
        # block (rows 1-3) stays centered vertically.
        bye.grid_rowconfigure(0, weight=1)
        bye.grid_rowconfigure(4, weight=1)
        bye.grid_columnconfigure(0, weight=1)

        logo_path = self._assets_dir() / "logo.png"
        if logo_path.exists():
            try:
                pil = Image.open(logo_path)
                ratio = pil.width / pil.height
                logo_h = 110
                logo_w = int(logo_h * ratio)
                img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(logo_w, logo_h))
                ctk.CTkLabel(bye, image=img, text="").grid(row=1, column=0, pady=(0, 10))
            except Exception:
                pass

        ctk.CTkLabel(bye, text="Até logo!", font=ctk.CTkFont(size=22, weight="bold")).grid(row=2, column=0)
        ctk.CTkLabel(bye, text="Obrigado por usar o Processador de DTFs.\nDesenvolvido por Tecnosup",
                     text_color="#9AA0A6", justify="center").grid(row=3, column=0, pady=(6, 0))

        self.update_idletasks()
        self.after(1500, self.destroy)

    def _reset(self):
        if self._worker and self._worker.is_alive():
            return
        self.path_var.set("")
        self.counts_label.configure(text="—", text_color="#9AA0A6")
        self.progress_bar.set(0)
        self.stage_label.configure(text="Aguardando...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self._last_output = None
