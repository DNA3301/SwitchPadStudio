"""Validated settings and transactional persistence under per-user APPDATA."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import tempfile
import math
from typing import Any

# Raw defaults for first-generation original Switch Pro as documented by pygame.
# Other vendors may use entirely different indexes; all values can be edited in GUI.
DEFAULT_RAW = {
    "axes": {"lx": 0, "ly": 1, "rx": 2, "ry": 3},
    "trigger_axes": {"lt": 4, "rt": 5},
    "dpad_axes": {"x": -1, "y": -1},
    "trigger_mode": "axis",
    # Raw Nintendo physical labels -> Xbox positional names (B bottom = Xbox A).
    "buttons": {"A": 1, "B": 0, "X": 3, "Y": 2, "LB": 9, "RB": 10,
                "BACK": 4, "START": 6, "LS": 7, "RS": 8, "GUIDE": 5,
                "LT": -1, "RT": -1,
                "DPAD_UP": 11, "DPAD_DOWN": 12, "DPAD_LEFT": 13, "DPAD_RIGHT": 14},
    "hat": -1,
    "axis_centers": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0},
}
UNASSIGNED_RAW = copy.deepcopy(DEFAULT_RAW)
for _group in ("axes", "trigger_axes", "buttons", "dpad_axes"):
    UNASSIGNED_RAW[_group] = dict.fromkeys(DEFAULT_RAW[_group], -1)

DEFAULT = {
    "version": 4,
    "enabled": True,
    "auto_select": True,
    "preferred_guid": "",
    "preferred_instance": -1,
    "deadzone": 0.12,
    "nintendo_letters": False,
    "rumble": True,
    "tray_on_close": True,
    "invert_lx": False, "invert_ly": False,
    "invert_rx": False, "invert_ry": False,
    "raw": DEFAULT_RAW,
    "raw_confirmed": False,
    "force_raw": False,
    "button_remap": {},
    "profiles": {},
}
PROFILE_KEYS = ("deadzone", "nintendo_letters", "rumble", "invert_lx", "invert_ly",
                "invert_rx", "invert_ry", "raw", "raw_confirmed", "force_raw", "button_remap")


def effective(settings: dict, guid: str) -> dict:
    """Profiles are scoped to SDL GUID (USB and Bluetooth may have different GUIDs)."""
    result = copy.deepcopy(settings)
    result.update(copy.deepcopy(settings.get("profiles", {}).get(guid, {})))
    return result


def config_root() -> Path:
    base = os.getenv("APPDATA")
    if not base:
        base = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(base) / "SwitchPadStudio"


def config_path() -> Path:
    return config_root() / "settings.json"


def _valid_int(value: Any, default: int, maximum: int = 127) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return n if -1 <= n <= maximum else default


def sanitize(raw: object, *, _profile: bool = False) -> dict:
    defaults = copy.deepcopy(DEFAULT)
    if not isinstance(raw, dict):
        return defaults
    for key in ("enabled", "auto_select", "nintendo_letters", "rumble",
                "tray_on_close", "invert_lx", "invert_ly", "invert_rx", "invert_ry",
                "raw_confirmed", "force_raw"):
        if type(raw.get(key)) is bool:
            defaults[key] = raw[key]
    if isinstance(raw.get("preferred_guid"), str):
        defaults["preferred_guid"] = raw["preferred_guid"][:128]
    defaults["preferred_instance"] = _valid_int(raw.get("preferred_instance"), -1, 2**31 - 1)
    try:
        deadzone = float(raw.get("deadzone", 0.12))
        if 0.0 <= deadzone <= 0.5:
            defaults["deadzone"] = round(deadzone, 3)
    except (ValueError, TypeError):
        pass
    raw_cfg = raw.get("raw")
    if isinstance(raw_cfg, dict):
        for group in ("axes", "trigger_axes", "buttons", "dpad_axes"):
            if isinstance(raw_cfg.get(group), dict):
                for name, default_val in DEFAULT_RAW[group].items():
                    defaults["raw"][group][name] = _valid_int(raw_cfg[group].get(name), default_val)
        defaults["raw"]["hat"] = _valid_int(raw_cfg.get("hat"), -1, 15)
        if raw_cfg.get("trigger_mode") in ("axis", "buttons", "signed", "inverted_signed", "combined"):
            defaults["raw"]["trigger_mode"] = raw_cfg["trigger_mode"]
        centers = raw_cfg.get("axis_centers", {})
        if isinstance(centers, dict):
            for key in defaults["raw"]["axis_centers"]:
                try:
                    value = float(centers.get(key, 0))
                    if math.isfinite(value) and -0.75 <= value <= 0.75:
                        defaults["raw"]["axis_centers"][key] = value
                except (TypeError, ValueError, OverflowError):
                    pass
        # Preserve explicitly saved 3.x mappings; fresh generic profiles require confirmation.
        if raw.get("version") == 3 and "raw_confirmed" not in raw:
            defaults["raw_confirmed"] = True
    from .mapping import BUTTONS
    remap = raw.get("button_remap", {})
    if isinstance(remap, dict):
        defaults["button_remap"] = {k: v for k, v in remap.items()
                                   if k in BUTTONS and v in (*BUTTONS, "DISABLED")}
    profiles = raw.get("profiles", {})
    if not _profile and isinstance(profiles, dict):
        for guid, profile in list(profiles.items())[:128]:
            if isinstance(guid, str) and 0 < len(guid) <= 128 and isinstance(profile, dict):
                clean = sanitize(profile, _profile=True)
                defaults["profiles"][guid] = {k: clean[k] for k in PROFILE_KEYS}
    return defaults


def load() -> dict:
    path = config_path()
    if not path.is_file():
        return copy.deepcopy(DEFAULT)
    try:
        return sanitize(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULT)


def save(settings: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="config_", suffix=".json.tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(sanitize(settings), f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
