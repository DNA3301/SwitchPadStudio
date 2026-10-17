"""Switch/SDL -> virtual Xbox (XInput) forwarding; all SDL work on worker thread.

Never injects input into a game's process. Driver installation is intentionally manual.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import copy
import logging
import os
import re
import threading
import time
from typing import Optional

from .mapping import NEUTRAL, PadState, translate, button_mask

LOGGER = logging.getLogger(__name__)
TARGET_HZ = 120
SCAN_PERIOD_S = 1.35

# Default matching for automatic mode. Others are available for manual selection.
SWITCH_NAME = re.compile(r"nintendo|switch|joy[ -]?con|pro[ -]?controller|powera|8bitdo|hori", re.I)
VIRTUAL_NAME = re.compile(r"xbox[ -]?360|xinput|virtual[ -]?(?:xbox|gamepad)|vigem", re.I)
VIRTUAL_VID_PID = {(0x045E, 0x028E), (0x045E, 0x02FF)}


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    instance_id: int
    name: str
    guid: str
    vid: int
    pid: int
    mapped: bool
    recommended: bool

    @property
    def title(self) -> str:
        kind = "SDL" if self.mapped else "RAW (configurazione necessaria)"
        return f"{self.name}  •  {kind}  •  {self.vid:04X}:{self.pid:04X}"


@dataclass
class EngineState:
    devices: list[DeviceInfo] = field(default_factory=list)
    selected: Optional[DeviceInfo] = None
    source: PadState = NEUTRAL
    translated: PadState = NEUTRAL
    status: str = "Avvio in corso"
    mode: str = "idle"          # idle, ready, active, missing_driver, error
    virtual_active: bool = False
    last_error: str = ""
    sdl_version: str = ""
    fps: float = 0.0
    raw_debug: str = ""


def _nint(joy, name: str) -> int:
    try:
        return int(getattr(joy, name)())
    except (AttributeError, ValueError, OSError):
        return 0


def classify(name: str, vid: int, pid: int) -> tuple[bool, bool]:
    """Returns (is_virtual_xinput, probably_switch). Avoid feedback loop."""
    is_virtual = bool(VIRTUAL_NAME.search(name)) or (vid, pid) in VIRTUAL_VID_PID
    likely_switch = not is_virtual and (vid == 0x057E or bool(SWITCH_NAME.search(name)))
    return is_virtual, likely_switch


def _safe_axis(ctrl, axis) -> int:
    try:
        return int(ctrl.get_axis(axis))
    except (ValueError, OSError, TypeError):
        return 0


def _safe_button(ctrl, button) -> bool:
    try:
        return bool(ctrl.get_button(button))
    except (ValueError, OSError, TypeError):
        return False


def _raw_axis(joy, index: int) -> float:
    try:
        if index < 0 or index >= joy.get_numaxes():
            return 0.0
        return float(joy.get_axis(index))
    except (ValueError, OSError, IndexError):
        return 0.0


def _raw_button(joy, index: int) -> bool:
    try:
        if index < 0 or index >= joy.get_numbuttons():
            return False
        return bool(joy.get_button(index))
    except (ValueError, OSError, IndexError):
        return False


def read_raw(joy, raw_config: dict) -> PadState:
    """Raw HID fallback; indexes configurable from UI. Not universal across clones."""
    axes = raw_config.get("axes", {})
    cfg_buttons = raw_config.get("buttons", {})
    pushed = {k for k, i in cfg_buttons.items()
              if k not in ("LT", "RT") and _raw_button(joy, int(i))}
    try:
        hi = int(raw_config.get("hat", -1))
        hx, hy = joy.get_hat(hi) if 0 <= hi < joy.get_numhats() else (0, 0)
    except (ValueError, OSError, IndexError):
        hx, hy = 0, 0
    if hy > 0: pushed.add("DPAD_UP")
    if hy < 0: pushed.add("DPAD_DOWN")
    if hx > 0: pushed.add("DPAD_RIGHT")
    if hx < 0: pushed.add("DPAD_LEFT")
    def stick(name):
        try: return _raw_axis(joy, int(axes.get(name, -1)))
        except (TypeError, ValueError): return 0.0
    if raw_config.get("trigger_mode") == "buttons":
        lt = float(_raw_button(joy, int(cfg_buttons.get("LT", -1))))
        rt = float(_raw_button(joy, int(cfg_buttons.get("RT", -1))))
    else:
        trigger_cfg = raw_config.get("trigger_axes", {})
        lt = max(0.0, min(1.0, _raw_axis(joy, int(trigger_cfg.get("lt", -1)))))
        rt = max(0.0, min(1.0, _raw_axis(joy, int(trigger_cfg.get("rt", -1)))))
    return PadState(buttons=frozenset(pushed),
                    lx=stick("lx"), ly=-stick("ly"),
                    rx=stick("rx"), ry=-stick("ry"), lt=lt, rt=rt)


def raw_debug(joy) -> str:
    try:
        btns = [str(i) for i in range(min(joy.get_numbuttons(), 48)) if joy.get_button(i)]
        axes = [f"{i}:{joy.get_axis(i):+.2f}" for i in range(min(joy.get_numaxes(), 12))]
        hats = [f"{i}:{joy.get_hat(i)}" for i in range(min(joy.get_numhats(), 4))]
        return f"Pulsanti [{', '.join(btns)}]  •  Assi [{', '.join(axes)}]  •  DPad [{', '.join(hats)}]"
    except (OSError, ValueError, RuntimeError):
        return "Non disponibile"


def read_sdl(ctrl, pygame) -> PadState:
    """SDL standardized Xbox-position face buttons; Nintendo letters are optional.

    SDL axes on sticks: Y+ is down, XInput Y+ is up.
    """
    names = {
        "A": "A", "B": "B", "X": "X", "Y": "Y",
        "LB": "LEFTSHOULDER", "RB": "RIGHTSHOULDER",
        "BACK": "BACK", "START": "START", "LS": "LEFTSTICK", "RS": "RIGHTSTICK",
        "GUIDE": "GUIDE", "DPAD_UP": "DPAD_UP", "DPAD_DOWN": "DPAD_DOWN",
        "DPAD_LEFT": "DPAD_LEFT", "DPAD_RIGHT": "DPAD_RIGHT",
    }
    buttons = set()
    for label, const_name in names.items():
        const = getattr(pygame, "CONTROLLER_BUTTON_" + const_name, None)
        if const is not None and _safe_button(ctrl, const):
            buttons.add(label)
    def axis(name):
        c = getattr(pygame, "CONTROLLER_AXIS_" + name, None)
        return _safe_axis(ctrl, c) if c is not None else 0
    lx, ly = axis("LEFTX") / 32767.0, -axis("LEFTY") / 32767.0
    rx, ry = axis("RIGHTX") / 32767.0, -axis("RIGHTY") / 32767.0
    lt, rt = axis("TRIGGERLEFT") / 32768.0, axis("TRIGGERRIGHT") / 32768.0
    # Digital ZL/ZR are exposed as SDL trigger axes for mapped Switch devices.
    return PadState(frozenset(buttons), lx, ly, rx, ry, lt, rt)


class PadEngine:
    def __init__(self, settings: dict):
        self._settings = copy.deepcopy(settings)
        self._lock = threading.RLock()
        self._state = EngineState()
        self._stopped = threading.Event()
        self._rescan = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._rumble_values = (0.0, 0.0)
        self._rumble_dirty = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stopped.clear()
        self._thread = threading.Thread(target=self._run, name="SwitchPad-Engine", daemon=True)
        self._thread.start()

    def stop(self):
        self._stopped.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def get_state(self) -> EngineState:
        with self._lock:
            return copy.deepcopy(self._state)

    def settings_snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._settings)

    def update_settings(self, settings: dict):
        with self._lock:
            self._settings = copy.deepcopy(settings)
        self._rescan.set()

    def refresh_devices(self):
        self._rescan.set()

    def _publish(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._state, key, value)

    def _rumble_callback(self, client, target, large, small, led, user_data):
        with self._lock:
            self._rumble_values = (max(0.0, min(1.0, large / 255.0)),
                                   max(0.0, min(1.0, small / 255.0)))
            self._rumble_dirty = True

    @staticmethod
    def _discover(pygame, controller_api) -> list[DeviceInfo]:
        out = []
        for i in range(pygame.joystick.get_count()):
            try:
                joy = pygame.joystick.Joystick(i)
                name = str(joy.get_name() or "Controller sconosciuto")
                vid, pid = _nint(joy, "get_vendor"), _nint(joy, "get_product")
                virtual, likely = classify(name, vid, pid)
                if virtual:
                    continue
                # Store instance ID, not shifting device index, to withstand hotplug.
                out.append(DeviceInfo(i, int(joy.get_instance_id()), name,
                                      str(joy.get_guid()), vid, pid,
                                      bool(controller_api.is_controller(i)), likely))
            except (OSError, ValueError, RuntimeError) as ex:
                LOGGER.debug("Skipping disconnected joystick %d: %s", i, ex)
        return out

    @staticmethod
    def _pick(devices: list[DeviceInfo], settings: dict) -> Optional[DeviceInfo]:
        if settings.get("auto_select", True):
            return next((dev for dev in devices if dev.recommended), None)
        guid = settings.get("preferred_guid", "")
        return next((dev for dev in devices if dev.guid == guid), None)

    @staticmethod
    def _write_virtual(pad, vg, state: PadState):
        pad.reset()
        mask = button_mask(state)
        if mask:
            pad.press_button(button=vg.XUSB_BUTTON(mask))
        pad.left_joystick_float(x_value_float=state.lx, y_value_float=state.ly)
        pad.right_joystick_float(x_value_float=state.rx, y_value_float=state.ry)
        pad.left_trigger_float(value_float=state.lt)
        pad.right_trigger_float(value_float=state.rt)
        pad.update()

    @staticmethod
    def _disconnect_virtual(pad):
        if pad is not None:
            try:
                pad.unregister_notification()
            except (AttributeError, OSError):
                pass
            try:
                pad.reset()
                pad.update()
            except (OSError, RuntimeError):
                pass

    def _run(self):
        # Environment hints MUST precede importing pygame/initializing SDL.
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_SWITCH", "1")
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_JOY_CONS", "1")
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_COMBINE_JOY_CONS", "1")
        os.environ["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] = "0"
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            import pygame
            from pygame._sdl2 import controller as controller_api
        except Exception as ex:
            LOGGER.exception("SDL loading failed")
            self._publish(status="pygame/SDL non disponibile", mode="error", last_error=str(ex))
            return
        pad = None
        vg = None
        source_joy = None
        source_ctrl = None
        connected_id = None
        connected_dev = None
        devices = []
        next_scan = 0.0
        next_virtual_attempt = 0.0
        last_tick = time.perf_counter()
        rumble_time = 0.0
        prev_rumble = (0.0, 0.0)
        try:
            pygame.display.init()
            # SDL event pump requires video initialization; window is hidden.
            pygame.display.set_mode((1, 1), flags=pygame.HIDDEN)
            pygame.joystick.init()
            controller_api.init()
            sdl_version = ".".join(str(part) for part in pygame.get_sdl_version())
            self._publish(sdl_version=sdl_version, status="Ricerca controller...", mode="idle")
            LOGGER.info("SDL initialized version %s", sdl_version)

            while not self._stopped.is_set():
                start = time.perf_counter()
                try:
                    pygame.event.pump()
                except pygame.error as ex:
                    LOGGER.warning("SDL event pump failed: %s", ex)
                cfg = self.settings_snapshot()
                force_scan = self._rescan.is_set()
                if force_scan:
                    self._rescan.clear()
                if force_scan or start >= next_scan:
                    try:
                        devices = self._discover(pygame, controller_api)
                    except Exception:
                        LOGGER.exception("Device enumeration failed")
                        devices = []
                    self._publish(devices=devices)
                    next_scan = start + SCAN_PERIOD_S

                chosen = self._pick(devices, cfg)
                # Disconnect source on unplug / explicit device change.
                if chosen is None or connected_id != chosen.instance_id:
                    if source_ctrl is not None:
                        try: source_ctrl.quit()
                        except Exception: pass
                        source_ctrl = None
                    if source_joy is not None:
                        try: source_joy.quit()
                        except Exception: pass
                        source_joy = None
                    connected_id = None
                    connected_dev = None
                    if pad is not None:
                        self._disconnect_virtual(pad)
                        pad = None
                        self._publish(virtual_active=False)
                    if chosen is not None:
                        try:
                            if chosen.mapped:
                                source_ctrl = controller_api.Controller(chosen.index)
                                source_joy = source_ctrl.as_joystick()
                            else:
                                source_joy = pygame.joystick.Joystick(chosen.index)
                            connected_id = chosen.instance_id
                            connected_dev = chosen
                            LOGGER.info("Connected %s (%s)", chosen.name, "mapped" if chosen.mapped else "RAW")
                        except Exception as ex:
                            self._publish(mode="error", status="Impossibile aprire il pad", last_error=str(ex))
                            LOGGER.exception("Source open failed")
                            connected_id = None
                            next_scan = start + 2.0

                if connected_id is None or source_joy is None:
                    self._publish(selected=None, source=NEUTRAL, translated=NEUTRAL, raw_debug="",
                                  virtual_active=False, mode="idle",
                                  status="Collega un pad Switch o selezionalo nell'elenco")
                else:
                    try:
                        sample = (read_sdl(source_ctrl, pygame) if source_ctrl is not None
                                  else read_raw(source_joy, cfg["raw"]))
                    except (ValueError, OSError, RuntimeError) as ex:
                        LOGGER.warning("Lost source input: %s", ex)
                        connected_id = None
                        next_scan = 0.0
                        continue
                    converted = translate(sample, deadzone=float(cfg["deadzone"]),
                                          nintendo_letters=bool(cfg["nintendo_letters"]),
                                          invert_lx=bool(cfg["invert_lx"]),
                                          invert_ly=bool(cfg["invert_ly"]),
                                          invert_rx=bool(cfg["invert_rx"]),
                                          invert_ry=bool(cfg["invert_ry"]))
                    if not cfg.get("enabled", True):
                        if pad is not None:
                            self._disconnect_virtual(pad)
                            pad = None
                        self._publish(mode="ready", status="Pad rilevato, emulazione disattivata", virtual_active=False)
                    else:
                        if pad is None and start >= next_virtual_attempt:
                            try:
                                if vg is None:
                                    import vgamepad as vg
                                pad = vg.VX360Gamepad()
                                self._publish(last_error="")
                                self._rumble_values = (0.0, 0.0)
                                try:
                                    pad.register_notification(callback_function=self._rumble_callback)
                                except Exception as ex:
                                    LOGGER.info("Rumble feedback unavailable: %s", ex)
                                LOGGER.info("Virtual Xbox controller connected")
                            except Exception as ex:
                                next_virtual_attempt = start + 6.0
                                reason = f"Controller Xbox virtuale non creato: {ex}"
                                LOGGER.warning("Virtual pad init failed: %s", ex)
                                self._publish(mode="missing_driver", status="Driver ViGEmBus mancante/non operativo",
                                              last_error=reason, virtual_active=False)
                        if pad is not None:
                            try:
                                self._write_virtual(pad, vg, converted)
                                self._publish(mode="active", virtual_active=True,
                                              status="CONNESSO • Xbox 360 virtuale attivo")
                            except Exception as ex:
                                LOGGER.exception("Virtual controller update failed")
                                self._publish(mode="error", status="Errore durante la traduzione XInput",
                                              last_error=str(ex), virtual_active=False)
                                self._disconnect_virtual(pad)
                                pad = None
                                next_virtual_attempt = start + 6.0

                    debug = raw_debug(source_joy) if source_ctrl is None else ""
                    self._publish(selected=connected_dev, source=sample, translated=converted, raw_debug=debug)
                    if source_ctrl is not None:
                        if not cfg.get("rumble", True):
                            self._rumble_values = (0.0, 0.0)
                        with self._lock:
                            rumble = self._rumble_values
                            rumble_dirty = self._rumble_dirty
                            self._rumble_dirty = False
                        if cfg.get("rumble", True) and rumble != (0.0, 0.0):
                            if rumble_dirty or start - rumble_time >= 0.20:
                                try:
                                    source_ctrl.rumble(rumble[0], rumble[1], 300)
                                except (ValueError, OSError, AttributeError) as ex:
                                    LOGGER.debug("Controller does not support rumble: %s", ex)
                                rumble_time = start
                        elif prev_rumble != (0.0, 0.0):
                            try: source_ctrl.stop_rumble()
                            except (OSError, AttributeError): pass
                        prev_rumble = rumble

                # Fixed-rate loop; no busy spinning.
                work = time.perf_counter() - start
                elapsed = start - last_tick
                last_tick = start
                if elapsed > 0.0:
                    with self._lock:
                        self._state.fps = round(1.0 / elapsed, 1)
                self._stopped.wait(max(0.001, 1 / TARGET_HZ - work))

        except Exception as ex:
            LOGGER.exception("Fatal engine exception")
            self._publish(mode="error", status="Errore del motore di input", last_error=str(ex))
        finally:
            self._disconnect_virtual(pad)
            try:
                if source_ctrl: source_ctrl.quit()
                if source_joy: source_joy.quit()
            except Exception: pass
            try:
                controller_api.quit()
                pygame.joystick.quit()
                pygame.display.quit()
            except Exception: pass
            self._publish(virtual_active=False)
            LOGGER.info("Engine thread stopped")
