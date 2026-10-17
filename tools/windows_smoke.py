"""Opt-in real Windows driver check. No button presses or installer.

Run from the repository root: python tools/windows_smoke.py
No physical controller evidence is inferred from this software-only check.
"""
from pathlib import Path
import os
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def main():
    if os.name != "nt":
        raise SystemExit("Windows required")
    import pygame
    from pygame._sdl2 import controller
    from switchpad.engine import PadEngine
    from switchpad.native import SDLIdentity, virtual_slot, is_vigem_path
    from switchpad.settings import DEFAULT
    from switchpad.diagnostics import xinput_slots
    pygame.display.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    pygame.joystick.init()
    controller.init()
    identity = SDLIdentity(pygame)
    pad = None
    try:
        assert identity.dll is not None, "SDL identity bridge unavailable"
        engine = PadEngine(DEFAULT)
        engine._identity = identity
        before = {d.instance_id for d in engine._discover(pygame, controller)}
        import vgamepad as vg
        pad = vg.VX360Gamepad()
        engine._prime_virtual(pad)
        slot = None
        virtual_seen = False
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            pygame.event.get()
            slot = virtual_slot(pad)
            virtual_seen = any(is_vigem_path(identity.read(i)[2]) is True
                               for i in range(pygame.joystick.get_count()))
            if slot is not None and virtual_seen:
                break
            time.sleep(.1)
        assert slot is not None, "No native XInput user index"
        assert virtual_seen, "ViGEm device identity not confirmed"
        engine._own_slot, engine._output_active = slot, True
        after = {d.instance_id for d in engine._discover(pygame, controller)}
        assert after <= before, "Output device leaked into source list"
        output = next((s for s in xinput_slots() if s["slot"] == slot + 1), None)
        assert output is not None, "XInput cannot see virtual output"
        assert all(output[k] == 0 for k in ("buttons", "lt", "rt", "lx", "ly", "rx", "ry"))
        print(f"PASS: SDL {pygame.get_sdl_version()}, native identity, neutral XInput output, feedback guard")
    finally:
        if pad is not None:
            pad.reset()
            pad.update()
            del pad
        controller.quit()
        pygame.quit()


if __name__ == "__main__":
    main()
