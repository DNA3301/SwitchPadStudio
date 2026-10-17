"""Validated settings and transactional persistence under per-user APPDATA."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import tempfile
from typing import Any

# Raw defaults for first-generation original Switch Pro as documented by pygame.
# Other vendors may use entirely different indexes; all values can be edited in GUI.
DEFAULT_RAW = {
    "axes": {"lx": 0, "ly": 1, "rx": 2, "ry": 3},
    "trigger_axes": {"lt": 4, "rt": 5},
    "trigger_mode": "axis",
    # Raw Nintendo physical labels -> Xbox positional names (B bottom = Xbox A).
    "buttons": {"A": 1, "B": 0, "X": 3, "Y": 2, "LB": 9, "RB": 10,
                "BACK": 4, "START": 6, "LS": 7, "RS": 8, "GUIDE": 5,
                "LT": -1, "RT": -1,
                "DPAD_UP": 11, "DPAD_DOWN": 12, "DPAD_LEFT": 13, "DPAD_RIGHT": 14},
    "hat": -1,
}
DEFAULT = {
    "version": 3,
    "enabled": True,
    "auto_select": True,
    "preferred_guid": "",
    "deadzone": 0.12,
    "nintendo_letters": False,
    "rumble": True,
    "tray_on_close": True,
    "invert_lx": False, "invert_ly": False,
    "invert_rx": False, "invert_ry": False,
    "raw": DEFAULT_RAW,
}


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


def sanitize(raw: object) -> dict:
    defaults = copy.deepcopy(DEFAULT)
    if not isinstance(raw, dict):
        return defaults
    for key in ("enabled", "auto_select", "nintendo_letters", "rumble",
                "tray_on_close", "invert_lx", "invert_ly", "invert_rx", "invert_ry"):
        if type(raw.get(key)) is bool:
            defaults[key] = raw[key]
    if isinstance(raw.get("preferred_guid"), str):
        defaults["preferred_guid"] = raw["preferred_guid"][:128]
    try:
        deadzone = float(raw.get("deadzone", 0.12))
        if 0.0 <= deadzone <= 0.5:
            defaults["deadzone"] = round(deadzone, 3)
    except (ValueError, TypeError):
        pass
    raw_cfg = raw.get("raw")
    if isinstance(raw_cfg, dict):
        for group in ("axes", "trigger_axes", "buttons"):
            if isinstance(raw_cfg.get(group), dict):
                for name, default_val in DEFAULT_RAW[group].items():
                    defaults["raw"][group][name] = _valid_int(raw_cfg[group].get(name), default_val)
        defaults["raw"]["hat"] = _valid_int(raw_cfg.get("hat"), -1, 15)
        if raw_cfg.get("trigger_mode") in ("axis", "buttons"):
            defaults["raw"]["trigger_mode"] = raw_cfg["trigger_mode"]
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
