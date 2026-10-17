import copy
import json
import os
import tempfile
import time
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from switchpad.engine import DeviceInfo, PadEngine, read_raw
from switchpad.mapping import PadState, translate
from switchpad.native import exclude_feedback
from switchpad.settings import DEFAULT, UNASSIGNED_RAW, effective, sanitize, save, load
from test_engine import MockJoy, MockController, MockVirtual


def device(instance=1, guid="pad-a", mapped=True, name="Generic USB Gamepad"):
    return DeviceInfo(instance - 1, instance, name, guid, 0, 0, mapped, False)


@contextmanager
def runtime(mapped=True, broken_driver=False):
    """Hotplug/event/driver fixture; no real hardware or driver imports."""
    import sys
    state = types.SimpleNamespace(connected=True, instance=42, events=[], pads=[], joy=MockJoy())
    state.joy.get_instance_id = lambda: state.instance
    state.joy.get_name = lambda: "Generic USB Gamepad"
    pygame = types.ModuleType("pygame")
    pygame.display = types.SimpleNamespace(init=lambda: None, quit=lambda: None, set_mode=lambda *a, **k: None)
    pygame.joystick = types.SimpleNamespace(init=lambda: None, quit=lambda: None,
        get_count=lambda: int(state.connected), Joystick=lambda i: state.joy)
    def get_events():
        events, state.events = state.events, []
        return events
    pygame.event = types.SimpleNamespace(pump=lambda: None, get=get_events)
    pygame.HIDDEN = 0
    pygame.error = RuntimeError
    pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED = 1, 2
    pygame.get_sdl_version = lambda: (2, 28, 4)
    for i, key in enumerate(("LEFTX", "LEFTY", "RIGHTX", "RIGHTY", "TRIGGERLEFT", "TRIGGERRIGHT")):
        setattr(pygame, "CONTROLLER_AXIS_" + key, i)
    controller = types.ModuleType("pygame._sdl2.controller")
    controller.init = controller.quit = lambda: None
    controller.is_controller = lambda i: mapped
    class Controller(MockController):
        def as_joystick(self): return state.joy
    controller.Controller = Controller
    sdl2 = types.ModuleType("pygame._sdl2")
    sdl2.controller = controller
    vg = types.ModuleType("vgamepad")
    def create():
        if broken_driver:
            raise OSError("Driver unavailable")
        pad = MockVirtual()
        state.pads.append(pad)
        return pad
    vg.VX360Gamepad, vg.XUSB_BUTTON = create, int
    modules = {"pygame": pygame, "pygame._sdl2": sdl2, "pygame._sdl2.controller": controller, "vgamepad": vg}
    with patch.dict(sys.modules, modules), patch("switchpad.engine.SDLIdentity", return_value=None):
        yield state


def eventually(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.005)
    return False


class UniversalSelectionTests(unittest.TestCase):
    def test_auto_accepts_all_families(self):
        for name in ("Xbox 360 Controller", "Xbox Series X", "DualSense", "PS4 Controller", "8BitDo", "USB Joystick"):
            with self.subTest(name=name):
                d = device(name=name)
                self.assertEqual(PadEngine._pick([d], DEFAULT), d)

    def test_prefers_mapped_over_unknown_raw(self):
        raw, mapped = device(mapped=False), device(2)
        self.assertEqual(PadEngine._pick([raw, mapped], DEFAULT), mapped)

    def test_auto_keeps_active_device_on_reorder(self):
        first, second = device(), device(2)
        self.assertEqual(PadEngine._pick([second, first], DEFAULT, 1), first)

    def test_manual_same_model_uses_instance_then_reconnects(self):
        first, second = device(), device(2)
        cfg = {**DEFAULT, "auto_select": False, "preferred_guid": "pad-a", "preferred_instance": 2}
        self.assertEqual(PadEngine._pick([first, second], cfg), second)
        reconnected = device(9)
        self.assertEqual(PadEngine._pick([reconnected], cfg), reconnected)

    def test_manual_missing_device_does_not_switch_to_another(self):
        cfg = {**DEFAULT, "auto_select": False, "preferred_guid": "absent"}
        self.assertIsNone(PadEngine._pick([device()], cfg))


class FeedbackTests(unittest.TestCase):
    def test_physical_xbox_not_rejected_by_vid_pid(self):
        with patch("switchpad.native.is_vigem_path", return_value=False):
            self.assertFalse(exclude_feedback("Xbox 360", 0x45E, 0x28E, "physical", 0, True))

    def test_virtual_bus_excluded_even_before_output(self):
        with patch("switchpad.native.is_vigem_path", return_value=True):
            self.assertTrue(exclude_feedback("Xbox 360", 0x45E, 0x28E, "virtual"))

    def test_own_xinput_slot_excluded(self):
        self.assertTrue(exclude_feedback("Xbox", 0, 0, "XInput#1", 1, True))
        self.assertFalse(exclude_feedback("Xbox", 0, 0, "XInput#2", 1, True))

    def test_unknown_slot_fails_closed_while_output_active(self):
        self.assertTrue(exclude_feedback("Xbox", 0, 0, "XInput#1", None, True))

    def test_ambiguous_identity_fails_closed(self):
        with patch("switchpad.native.is_vigem_path", return_value=None):
            self.assertTrue(exclude_feedback("Xbox", 0x45E, 0x28E, "", None, True))
            self.assertFalse(exclude_feedback("Xbox", 0x45E, 0x28E, "", None, False))

    def test_retired_virtual_instance_cannot_become_source(self):
        with runtime() as state:
            engine = PadEngine(DEFAULT)
            engine._excluded_ids.add(42)
            import pygame
            from pygame._sdl2 import controller
            self.assertEqual(engine._discover(pygame, controller), [])


class RawCompatibilityTests(unittest.TestCase):
    def config(self, mode="axis"):
        raw = copy.deepcopy(UNASSIGNED_RAW)
        raw["trigger_mode"] = mode
        raw["trigger_axes"] = {"lt": 4, "rt": 5}
        return raw

    def test_signed_trigger_rest_and_full_range(self):
        joy = MockJoy()
        for value, expected in ((-1, 0), (0, .5), (1, 1)):
            joy.get_axis = lambda i, v=value: v
            self.assertEqual(read_raw(joy, self.config("signed")).lt, expected)

    def test_inverted_signed_trigger_range(self):
        joy = MockJoy()
        for value, expected in ((1, 0), (0, .5), (-1, 1)):
            joy.get_axis = lambda i, v=value: v
            self.assertEqual(read_raw(joy, self.config("inverted_signed")).rt, expected)

    def test_combined_trigger_axis(self):
        joy = MockJoy()
        raw = self.config("combined")
        raw["trigger_axes"] = {"lt": 4, "rt": 4}
        for value, expected in ((0, (0, 0)), (.8, (.8, 0)), (-.6, (0, .6))):
            joy.get_axis = lambda i, v=value: v
            result = read_raw(joy, raw)
            self.assertEqual((result.lt, result.rt), expected)

    def test_disabled_trigger_is_zero_in_all_modes(self):
        for mode in ("axis", "signed", "inverted_signed", "combined", "buttons"):
            raw = copy.deepcopy(UNASSIGNED_RAW)
            raw["trigger_mode"] = mode
            self.assertEqual(read_raw(MockJoy(), raw), PadState())

    def test_out_of_range_trigger_is_zero_in_signed_mode(self):
        raw = self.config("signed")
        raw["trigger_axes"] = {"lt": 90, "rt": -1}
        self.assertEqual(read_raw(MockJoy(), raw).lt, 0)

    def test_digital_triggers_and_hat_diagonal(self):
        raw = self.config("buttons")
        raw["buttons"]["LT"] = 0
        raw["buttons"]["RT"] = 1
        raw["hat"] = 0
        state = read_raw(MockJoy(), raw)
        self.assertEqual((state.lt, state.rt), (1, 0))
        self.assertEqual(state.buttons, frozenset({"DPAD_RIGHT", "DPAD_UP"}))

    def test_axis_center_calibration_retains_endpoints(self):
        raw = copy.deepcopy(UNASSIGNED_RAW)
        raw["axes"]["lx"] = 0
        raw["axis_centers"]["lx"] = .2
        joy = MockJoy()
        for value, expected in ((.2, 0), (1, 1), (-1, -1)):
            joy.get_axis = lambda i, v=value: v
            self.assertAlmostEqual(read_raw(joy, raw).lx, expected)

    def test_disabled_stick_ignores_saved_center(self):
        raw = copy.deepcopy(UNASSIGNED_RAW)
        raw["axis_centers"]["lx"] = .3
        self.assertEqual(read_raw(MockJoy(), raw).lx, 0)

    def test_arbitrary_logical_remapping_is_simultaneous(self):
        state = translate(PadState(frozenset({"A", "B", "LB"})), button_remap={"A": "B", "B": "A", "LB": "DISABLED"})
        self.assertEqual(state.buttons, frozenset({"A", "B"}))

    def test_analog_axis_dpad_supports_diagonals(self):
        raw = copy.deepcopy(UNASSIGNED_RAW)
        raw["dpad_axes"] = {"x": 2, "y": 3}
        joy = MockJoy()
        joy.get_axis = lambda index: 1 if index == 2 else -1
        self.assertEqual(read_raw(joy, raw).buttons, frozenset({"DPAD_RIGHT", "DPAD_UP"}))


class ProfileTests(unittest.TestCase):
    def test_profiles_do_not_leak_between_devices(self):
        cfg = sanitize({"profiles": {"one": {"deadzone": .3}, "two": {"deadzone": .05}}})
        self.assertEqual(effective(cfg, "one")["deadzone"], .3)
        self.assertEqual(effective(cfg, "two")["deadzone"], .05)
        effective(cfg, "one")["raw"]["buttons"]["A"] = 100
        self.assertEqual(effective(cfg, "two")["raw"]["buttons"]["A"], 1)

    def test_profiles_roundtrip(self):
        cfg = sanitize({"profiles": {"usb": {"force_raw": True, "raw_confirmed": True, "button_remap": {"A": "X"}}}})
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            save(cfg)
            self.assertEqual(load(), cfg)

    def test_v3_explicit_raw_migration(self):
        cfg = sanitize({"version": 3, "raw": {"buttons": {"A": 27}}})
        self.assertEqual(cfg["version"], 4)
        self.assertTrue(cfg["raw_confirmed"])
        self.assertEqual(cfg["raw"]["buttons"]["A"], 27)

    def test_fresh_raw_requires_confirmation(self):
        self.assertFalse(sanitize({})["raw_confirmed"])

    def test_invalid_profile_values_are_sanitized(self):
        cfg = sanitize({"profiles": {"pad": {"deadzone": float("nan"), "button_remap": {"BAD": "A", "A": []},
                        "raw": {"axis_centers": {"lx": float("inf"), "ly": -.2}}}}})
        profile = effective(cfg, "pad")
        self.assertEqual(profile["deadzone"], .12)
        self.assertEqual(profile["button_remap"], {})
        self.assertEqual(profile["raw"]["axis_centers"]["lx"], 0)
        self.assertEqual(profile["raw"]["axis_centers"]["ly"], -.2)

    def test_profile_cannot_override_global_enable_or_embed_profiles(self):
        cfg = sanitize({"enabled": False, "profiles": {"pad": {"enabled": True, "profiles": {"nested": {}}}}})
        self.assertFalse(effective(cfg, "pad")["enabled"])
        self.assertNotIn("profiles", cfg["profiles"]["pad"])


class EngineLifecycleTests(unittest.TestCase):
    def test_unknown_raw_has_preview_without_virtual_output(self):
        with runtime(mapped=False) as state:
            engine = PadEngine(copy.deepcopy(DEFAULT))
            engine.start()
            try:
                self.assertTrue(eventually(lambda: engine.get_state().selected is not None))
                self.assertEqual(engine.get_state().mode, "ready")
                self.assertFalse(state.pads)
                cfg = copy.deepcopy(DEFAULT)
                cfg["profiles"]["abc123"] = {"raw_confirmed": True}
                engine.update_settings(cfg)
                self.assertTrue(eventually(lambda: engine.get_state().virtual_active))
            finally:
                engine.stop()

    def test_hot_unplug_neutralizes_and_reconnects_new_instance(self):
        with runtime() as state:
            engine = PadEngine(copy.deepcopy(DEFAULT))
            engine.start()
            try:
                self.assertTrue(eventually(lambda: engine.get_state().virtual_active))
                first = state.pads[0]
                state.connected = False
                state.events.append(types.SimpleNamespace(type=2, instance_id=42))
                self.assertTrue(eventually(lambda: engine.get_state().selected is None))
                self.assertFalse(engine.get_state().virtual_active)
                self.assertTrue(first.closed)
                self.assertEqual(first.report, {})
                state.instance, state.connected = 99, True
                state.events.append(types.SimpleNamespace(type=1))
                self.assertTrue(eventually(lambda: engine.get_state().virtual_active))
                self.assertEqual(engine.get_state().selected.instance_id, 99)
            finally:
                engine.stop()

    def test_missing_driver_retains_live_diagnostics(self):
        with runtime(broken_driver=True):
            engine = PadEngine(copy.deepcopy(DEFAULT))
            engine.start()
            try:
                self.assertTrue(eventually(lambda: engine.get_state().mode == "missing_driver"))
                self.assertIsNotNone(engine.get_state().selected)
                self.assertTrue(engine.get_state().raw_axes)
            finally:
                engine.stop()

    def test_force_raw_reopens_mapped_source_and_applies_profile(self):
        with runtime() as state:
            cfg = copy.deepcopy(DEFAULT)
            engine = PadEngine(cfg)
            engine.start()
            try:
                self.assertTrue(eventually(lambda: engine.get_state().virtual_active))
                cfg["profiles"]["abc123"] = {"force_raw": True, "raw_confirmed": True,
                    "raw": copy.deepcopy(DEFAULT["raw"]), "deadzone": 0, "button_remap": {"B": "X"}}
                engine.update_settings(cfg)
                self.assertTrue(eventually(lambda: "X" in engine.get_state().translated.buttons))
                self.assertAlmostEqual(engine.get_state().translated.lx, .5)
            finally:
                engine.stop()

    def test_source_read_failure_releases_output_without_killing_worker(self):
        with runtime() as state:
            engine = PadEngine(copy.deepcopy(DEFAULT))
            engine.start()
            try:
                self.assertTrue(eventually(lambda: engine.get_state().virtual_active))
                first = state.pads[0]
                def unplug(): raise RuntimeError("Disconnected")
                state.joy.get_numaxes = unplug
                self.assertTrue(eventually(lambda: first.closed))
                self.assertFalse(engine.get_state().virtual_active)
                self.assertTrue(engine._thread.is_alive())
            finally:
                engine.stop()


if __name__ == "__main__":
    unittest.main()
