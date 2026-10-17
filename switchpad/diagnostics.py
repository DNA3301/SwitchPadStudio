"""Windows-specific, read-only diagnostics and optional startup registration."""
from __future__ import annotations
import ctypes
import os
import sys
from pathlib import Path

DRIVER_RELEASES_URL = "https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0"
DRIVER_EOL_URL = "https://docs.nefarius.at/projects/ViGEm/End-of-Life/"
HIDHIDE_URL = "https://docs.nefarius.at/projects/HidHide/Simple-Setup-Guide/"


def xinput_slots() -> list[dict]:
    if os.name != "nt":
        return []
    try:
        class XInputGamepad(ctypes.Structure):
            _fields_ = [("buttons", ctypes.c_ushort), ("lt", ctypes.c_ubyte),
                        ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short),
                        ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]

        class XInputState(ctypes.Structure):
            _fields_ = [("packet", ctypes.c_uint32), ("gamepad", XInputGamepad)]

        dll = ctypes.WinDLL("xinput1_4.dll")
        method = dll.XInputGetState
        method.argtypes = (ctypes.c_uint, ctypes.POINTER(XInputState))
        method.restype = ctypes.c_uint
        slots = []
        for idx in range(4):
            state = XInputState()
            if method(idx, ctypes.byref(state)) == 0:
                slots.append({"slot": idx + 1, "buttons": int(state.gamepad.buttons),
                              "lt": int(state.gamepad.lt), "rt": int(state.gamepad.rt),
                              "lx": int(state.gamepad.lx), "ly": int(state.gamepad.ly),
                              "rx": int(state.gamepad.rx), "ry": int(state.gamepad.ry)})
        return slots
    except (OSError, AttributeError):
        return []


def driver_present() -> bool | None:
    """Presence hint only; only successful virtual pad creation proves usability."""
    if os.name != "nt":
        return None
    try:
        import winreg
        key_paths = [r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"]
        for path in key_paths:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as root:
                count = winreg.QueryInfoKey(root)[0]
                for i in range(count):
                    try:
                        with winreg.OpenKey(root, winreg.EnumKey(root, i)) as k:
                            name = str(winreg.QueryValueEx(k, "DisplayName")[0]).lower()
                            if "nefarius virtual gamepad emulation" in name or "vigembus" in name:
                                return True
                    except OSError:
                        pass
        return False
    except OSError:
        return None


def startup_registered() -> bool:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            path, _ = winreg.QueryValueEx(k, "SwitchPadStudio")
        return path.strip('"') == str(Path(sys.executable).resolve())
    except OSError:
        return False


def set_startup(enabled: bool) -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise RuntimeError("Avvio automatico disponibile solo nella versione EXE compilata per Windows.")
    import winreg
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0,
                            winreg.KEY_SET_VALUE) as reg:
        if enabled:
            winreg.SetValueEx(reg, "SwitchPadStudio", 0, winreg.REG_SZ,
                              '"' + str(Path(sys.executable).resolve()) + '"')
        else:
            try:
                winreg.DeleteValue(reg, "SwitchPadStudio")
            except FileNotFoundError:
                pass


def open_joy() -> None:
    if os.name == "nt":
        os.startfile("joy.cpl")


def open_bluetooth() -> None:
    if os.name == "nt":
        os.startfile("ms-settings:bluetooth")
