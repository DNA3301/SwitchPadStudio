"""Pure input normalization/translation. No pygame, drivers, GUI or OS access."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import hypot
from typing import FrozenSet

BUTTONS = ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "LS", "RS", "GUIDE",
           "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT")

# XUSB button masks, stable values defined by Microsoft XInput.
XUSB_MASKS = {
    "DPAD_UP": 0x0001, "DPAD_DOWN": 0x0002,
    "DPAD_LEFT": 0x0004, "DPAD_RIGHT": 0x0008,
    "START": 0x0010, "BACK": 0x0020,
    "LS": 0x0040, "RS": 0x0080,
    "LB": 0x0100, "RB": 0x0200,
    "GUIDE": 0x0400,
    "A": 0x1000, "B": 0x2000, "X": 0x4000, "Y": 0x8000,
}


@dataclass(frozen=True)
class PadState:
    """Source values normalized so Y+ means up, unlike SDL's Y+ down."""
    buttons: FrozenSet[str] = field(default_factory=frozenset)
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    lt: float = 0.0
    rt: float = 0.0


NEUTRAL = PadState()


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def radial_deadzone(x: float, y: float, threshold: float) -> tuple[float, float]:
    """Normalize radial deadzone without discontinuity or diagonal overshoot."""
    x, y = clamp(x), clamp(y)
    threshold = clamp(threshold, 0.0, 0.95)
    radius = hypot(x, y)
    if radius <= threshold:
        return 0.0, 0.0
    if radius == 0.0:
        return 0.0, 0.0
    radius_after = min(1.0, (radius - threshold) / (1.0 - threshold))
    return clamp(x / radius * radius_after), clamp(y / radius * radius_after)


def translate(state: PadState, deadzone: float = 0.12, nintendo_letters: bool = False,
              invert_lx: bool = False, invert_ly: bool = False,
              invert_rx: bool = False, invert_ry: bool = False) -> PadState:
    lx, ly = radial_deadzone(-state.lx if invert_lx else state.lx,
                              -state.ly if invert_ly else state.ly, deadzone)
    rx, ry = radial_deadzone(-state.rx if invert_rx else state.rx,
                              -state.ry if invert_ry else state.ry, deadzone)
    buttons = set(state.buttons)
    if nintendo_letters:
        # SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0 gives Xbox POSITION by default.
        # Nintendo LABELS are the opposite face-button pairing.
        remap = {"A": "B", "B": "A", "X": "Y", "Y": "X"}
        buttons = {remap.get(key, key) for key in buttons}
    return PadState(buttons=frozenset(buttons), lx=lx, ly=ly, rx=rx, ry=ry,
                    lt=clamp(state.lt, 0.0, 1.0), rt=clamp(state.rt, 0.0, 1.0))


def button_mask(state: PadState) -> int:
    out = 0
    for btn in state.buttons:
        out |= XUSB_MASKS.get(btn, 0)
    return out


def state_text(state: PadState) -> str:
    btn = ", ".join(sorted(state.buttons)) or "nessuno"
    return (f"Tasti: {btn} | SX ({state.lx:+.2f}, {state.ly:+.2f})"
            f" | DX ({state.rx:+.2f}, {state.ry:+.2f}) | LT {state.lt:.2f} RT {state.rt:.2f}")
