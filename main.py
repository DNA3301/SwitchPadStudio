"""SwitchPad Studio entrypoint."""
from __future__ import annotations
import ctypes
import logging
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_SWITCH", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_JOY_CONS", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_COMBINE_JOY_CONS", "1")
os.environ["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] = "0"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from switchpad.settings import config_root
from switchpad.ui import SwitchPadApp


def start_logging():
    root = config_root() / "logs"
    root.mkdir(parents=True, exist_ok=True)
    log = root / "session.log"
    try:
        if log.exists() and log.stat().st_size > 2_000_000:
            old = log.with_name("session.previous.log")
            os.replace(log, old)
    except OSError:
        pass
    logging.basicConfig(filename=str(log), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        encoding="utf-8")
    logging.info("Starting SwitchPad Studio v4.0.0")


def windows_single_instance():
    if os.name != "nt":
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, "Local\\SwitchPadStudio_OneInstance")
    if not mutex:
        return None
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(mutex)
        return False
    return mutex  # reference kept alive until program exit


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--verify-install":
        from switchpad.verification import verify_install
        verify_install(Path(sys.argv[2]))
        return
    start_logging()
    mutex = windows_single_instance()
    if mutex is False:
        temp_root = tk.Tk(); temp_root.withdraw()
        messagebox.showinfo("SwitchPad Studio", "SwitchPad Studio è già in esecuzione. Cerca l'icona nell'area di notifica.")
        temp_root.destroy()
        return
    if os.name != "nt":
        print("Questa applicazione richiede Windows 10/11 per l'emulazione Xbox. Test non eseguibile su questo sistema.")
        return
    root = tk.Tk()
    try:
        SwitchPadApp(root)
        root.mainloop()
    except Exception:
        logging.exception("Fatal UI exception")
        messagebox.showerror("SwitchPad Studio", "Errore imprevisto. Controlla il file session.log in AppData\\Roaming\\SwitchPadStudio\\logs")
        raise
    finally:
        if mutex and mutex is not False:
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
