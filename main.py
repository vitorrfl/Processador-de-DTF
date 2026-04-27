"""DTF Processor - entrypoint."""
import sys


def _ensure_single_instance() -> bool:
    """
    Returns True if this is the only running instance.
    Uses a Windows named mutex; fallback returns True on non-Windows.
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        # Hold the handle for the whole process lifetime
        global _mutex_handle
        _mutex_handle = kernel32.CreateMutexW(None, True, "Tecnosup.ProcessadorDTFs.SingleInstance")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            return False
        return True
    except Exception:
        return True


def _show_already_running_message():
    """Show a friendly dialog telling the user the app is already open."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "O Processador de DTFs já está aberto.\n\nVerifique a barra de tarefas.",
            "Processador de DTFs",
            0x00000040 | 0x00001000,  # MB_ICONINFORMATION | MB_SYSTEMMODAL
        )
    except Exception:
        pass


if __name__ == "__main__":
    if not _ensure_single_instance():
        _show_already_running_message()
        sys.exit(0)

    from src.app import App
    App().mainloop()
