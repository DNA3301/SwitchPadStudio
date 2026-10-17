"""Exercise actual Tk widgets with a fake engine; no hardware or settings writes."""
import copy
import tkinter as tk
import unittest
from unittest.mock import patch

from switchpad.engine import EngineState
from switchpad.settings import DEFAULT, effective, UNASSIGNED_RAW
from switchpad.ui import SwitchPadApp
from test_universal import device


class FakeEngine:
    def __init__(self, cfg):
        self.state = EngineState()
        self.cfg = cfg
    def start(self): pass
    def stop(self): pass
    def update_settings(self, cfg): self.cfg = copy.deepcopy(cfg)
    def get_state(self): return copy.deepcopy(self.state)
    def refresh_devices(self): pass


class UITests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as ex:
            self.skipTest(str(ex))
        self.root.withdraw()
        self.patches = [patch("switchpad.ui.PadEngine", FakeEngine),
                        patch("switchpad.ui.storage.load", return_value=copy.deepcopy(DEFAULT)),
                        patch("switchpad.ui.storage.save"),
                        patch.object(SwitchPadApp, "_init_tray"),
                        patch("switchpad.ui.messagebox.showinfo"),
                        patch("switchpad.ui.messagebox.showerror")]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.app = SwitchPadApp(self.root)
        self.addCleanup(self.app._quit)

    def select(self, guid="one", mapped=False):
        d = device(guid=guid, mapped=mapped)
        self.app.engine.state.selected = d
        self.app.engine.state.devices = [d]
        self.app._refresh()

    def test_all_tabs_construct_and_switch(self):
        self.assertEqual(len(self.app.tabs.tabs()), 3)
        for tab in self.app.tabs.tabs():
            self.app.tabs.select(tab)
            self.root.update_idletasks()
        self.assertIn("4.0", self.root.title())

    def test_new_generic_profile_starts_unassigned(self):
        self.select()
        cfg = self.app._config()
        self.assertEqual(cfg["raw"], UNASSIGNED_RAW)
        self.assertFalse(cfg["raw_confirmed"])

    def test_legacy_global_raw_cannot_enable_an_unrelated_generic_pad(self):
        self.app.settings["raw_confirmed"] = True
        self.select("new-generic")
        self.assertFalse(self.app._config()["raw_confirmed"])
        self.assertEqual(self.app._config()["raw"], UNASSIGNED_RAW)

    def test_raw_save_requires_a_connected_device(self):
        self.app._save_raw()
        self.assertFalse(self.app.settings["raw_confirmed"])

    def test_reconnected_manual_device_is_displayed_as_manual(self):
        self.app.settings.update(auto_select=False, preferred_guid="one", preferred_instance=99)
        self.select("one")
        self.assertIn("ID 1", self.app.device_var.get())

    def test_switching_controllers_restores_separate_options(self):
        self.select("one")
        self.app._update_setting("deadzone", .3)
        self.app._remap_button("A", "X")
        self.select("two")
        self.assertEqual(self.app._config()["deadzone"], .12)
        self.app._update_setting("deadzone", .05)
        self.select("one")
        self.assertEqual(self.app.deadzone_var.get(), .3)
        self.assertEqual(self.app.remap_vars["A"].get(), "X")

    def test_raw_save_is_atomic_when_one_index_is_invalid(self):
        self.select()
        before = copy.deepcopy(self.app._config()["raw"])
        self.app.raw_fields[("axes", "lx")].set("9")
        self.app.raw_fields[("axes", "ry")].set("bad")
        self.app._save_raw()
        self.assertEqual(self.app._config()["raw"], before)
        self.assertFalse(self.app._config()["raw_confirmed"])

    def test_raw_save_persists_hat_and_signed_triggers(self):
        self.select()
        self.app.raw_hat.set("0")
        self.app.raw_trigger_mode.set("Assi -1 → +1")
        self.app.raw_fields[("trigger_axes", "lt")].set("4")
        self.app._save_raw()
        cfg = self.app._config()
        self.assertTrue(cfg["raw_confirmed"])
        self.assertEqual(cfg["raw"]["hat"], 0)
        self.assertEqual(cfg["raw"]["trigger_mode"], "signed")

    def test_button_learning_pauses_then_restores_emulation(self):
        self.select()
        st = self.app.engine.state
        st.raw_buttons = (False, False, False)
        self.app._start_learn("buttons", "A")
        self.assertFalse(self.app.settings["enabled"])
        st.raw_buttons = (False, False, True)
        self.app._poll_learn(st)
        self.assertEqual(self.app.raw_fields[("buttons", "A")].get(), "2")
        self.assertTrue(self.app.settings["enabled"])

    def test_hat_learning_clears_duplicate_dpad_buttons(self):
        self.select()
        self.app._start_learn("buttons", "DPAD_UP")
        self.app.engine.state.raw_hats = ((0, 1),)
        self.app._poll_learn(self.app.engine.state)
        self.assertEqual(self.app.raw_hat.get(), "0")
        self.assertEqual(self.app.raw_fields[("buttons", "DPAD_UP")].get(), "-1")

    def test_axis_learning_uses_change_from_rest(self):
        self.select()
        self.app.engine.state.raw_axes = (0, 0, -1)
        self.app._start_learn("trigger_axes", "lt")
        self.app.engine.state.raw_axes = (0, 0, 1)
        self.app._poll_learn(self.app.engine.state)
        self.assertEqual(self.app.raw_fields[("trigger_axes", "lt")].get(), "2")

    def test_profile_change_cancels_learning_and_restores_output_setting(self):
        self.select("one")
        self.app._start_learn("buttons", "A")
        self.select("two")
        self.assertIsNone(self.app._learn)
        self.assertTrue(self.app.settings["enabled"])

    def test_calibration_rejects_displaced_stick(self):
        self.select()
        self.app.raw_fields[("axes", "lx")].set("0")
        self.app.engine.state.raw_axes = (1,)
        self.app._calibrate()
        self.assertEqual(self.app._config()["raw"]["axis_centers"]["lx"], 0)


if __name__ == "__main__":
    unittest.main()
