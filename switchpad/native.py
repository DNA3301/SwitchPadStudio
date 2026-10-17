"""Read-only SDL/Windows identity bridge, used only during enumeration.

pygame exposes neither VID/PID nor device paths. Never identify a virtual pad
from Microsoft's VID/PID alone: real Xbox 360 controllers use the same IDs.
"""
from __future__ import annotations

import ctypes as ct
import os
import sys
from pathlib import Path


class SDLIdentity:
    def __init__(self, pygame):
        self.dll = None
        if os.name != "nt":
            return
        try:
            candidates = [Path(pygame.__file__).parent / "SDL2.dll"]
            if getattr(sys, "frozen", False):
                candidates.append(Path(sys._MEIPASS) / "SDL2.dll")
            location = next((p for p in candidates if p.is_file()), None)
            if location is None:
                return
            dll = ct.CDLL(str(location))
            for name in ("SDL_JoystickGetDeviceVendor", "SDL_JoystickGetDeviceProduct"):
                fn = getattr(dll, name)
                fn.argtypes = [ct.c_int]
                fn.restype = ct.c_uint16
            dll.SDL_JoystickPathForIndex.argtypes = [ct.c_int]
            dll.SDL_JoystickPathForIndex.restype = ct.c_char_p
            self.dll = dll
        except (OSError, AttributeError, TypeError):
            pass

    def read(self, index):
        if self.dll is None:
            return 0, 0, ""
        path = self.dll.SDL_JoystickPathForIndex(index)
        return (self.dll.SDL_JoystickGetDeviceVendor(index),
                self.dll.SDL_JoystickGetDeviceProduct(index),
                path.decode("utf-8", "replace") if path else "")


def is_vigem_path(path: str) -> bool | None:
    """Follow the actual PnP parents. None means identity is unavailable."""
    if os.name != "nt" or not path.startswith("\\\\?\\"):
        return None
    # SDL's HID path contains the instance ID before the interface-class GUID.
    parts = path[4:].split("#")
    if len(parts) < 3:
        return None
    instance = "\\".join(parts[:3])
    try:
        cm = ct.WinDLL("cfgmgr32")
        cm.CM_Locate_DevNodeW.argtypes = [ct.POINTER(ct.c_ulong), ct.c_wchar_p, ct.c_ulong]
        cm.CM_Get_Parent.argtypes = [ct.POINTER(ct.c_ulong), ct.c_ulong, ct.c_ulong]
        cm.CM_Get_Device_IDW.argtypes = [ct.c_ulong, ct.c_wchar_p, ct.c_ulong, ct.c_ulong]
        cm.CM_Get_DevNode_Registry_PropertyW.argtypes = [ct.c_ulong, ct.c_ulong,
                                                       ct.POINTER(ct.c_ulong), ct.c_void_p,
                                                       ct.POINTER(ct.c_ulong), ct.c_ulong]
        node = ct.c_ulong()
        if cm.CM_Locate_DevNodeW(ct.byref(node), instance, 0):
            return None
        for _ in range(16):
            buf = ct.create_unicode_buffer(512)
            if cm.CM_Get_Device_IDW(node, buf, len(buf), 0):
                return None
            if "VIGEM" in buf.value.upper():
                return True
            # ViGEmBus often has a generic ROOT\SYSTEM instance ID; its driver
            # service is the authoritative identifier, not the friendly name.
            service = ct.create_unicode_buffer(512)
            size, kind = ct.c_ulong(ct.sizeof(service)), ct.c_ulong()
            if cm.CM_Get_DevNode_Registry_PropertyW(node, 5, ct.byref(kind), service,
                                                   ct.byref(size), 0) == 0:
                if "VIGEM" in service.value.upper():
                    return True
            parent = ct.c_ulong()
            if cm.CM_Get_Parent(ct.byref(parent), node, 0):
                return False
            node = parent
    except (OSError, AttributeError):
        pass
    return None


def virtual_slot(pad) -> int | None:
    """ViGEm's target index is NOT the XInput slot. Query the native user index."""
    try:
        from vgamepad.win import vigem_client as api
        slot = ct.c_ulong()
        result = api.vigem_target_x360_get_user_index(pad._busp, pad._devicep, ct.byref(slot))
        if result == 0x20000000 and slot.value < 4:  # VIGEM_ERROR_NONE
            return slot.value
    except (ImportError, AttributeError, OSError):
        pass
    return None


def exclude_feedback(name, vid, pid, path, own_slot=None, output_active=False):
    if "vigem" in name.lower() or "virtual" in name.lower():
        return True
    bus = is_vigem_path(path)
    if bus is True:
        return True
    if path.lower().startswith("xinput#"):
        try:
            slot = int(path.split("#", 1)[1])
        except ValueError:
            return True
        return slot == own_slot or (output_active and own_slot is None)
    # Fail closed for an ambiguous Xbox output if the native identity is unavailable.
    return bool(output_active and bus is None and (vid, pid) in {(0x045E, 0x028E), (0x045E, 0x02FF)})
