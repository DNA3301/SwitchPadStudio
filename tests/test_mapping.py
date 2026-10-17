import math
import unittest
from switchpad.mapping import PadState, clamp, radial_deadzone, translate, button_mask


class MappingTests(unittest.TestCase):
    def test_idle_stays_idle(self):
        s = translate(PadState(), deadzone=.12)
        self.assertEqual((s.lx, s.ly, s.rx, s.ry, s.lt, s.rt), (0,0,0,0,0,0))

    def test_radial_deadzone_removes_drift(self):
        self.assertEqual(radial_deadzone(.05, -.07, .12), (0, 0))

    def test_full_stick_saturates_at_one(self):
        x,y=radial_deadzone(1, 1, .15)
        self.assertAlmostEqual(math.hypot(x, y), 1, places=6)
        self.assertAlmostEqual(x,y)

    def test_half_stick_scales(self):
        x,y=radial_deadzone(.5,0,.1)
        self.assertAlmostEqual(x, .4/.9)
        self.assertEqual(y, 0)

    def test_inverted_axes(self):
        s=translate(PadState(lx=.9,ly=-.9,rx=.9,ry=-.9),0,invert_lx=True,invert_ry=True)
        self.assertTrue(s.lx<0 and s.ry>0)
        self.assertTrue(s.ly<0 and s.rx>0)

    def test_nintendo_labels_swaps_faces_only(self):
        s=translate(PadState(frozenset({'A','X','LB','DPAD_UP'})), 0, nintendo_letters=True)
        self.assertEqual(s.buttons, frozenset({'B','Y','LB','DPAD_UP'}))

    def test_negative_trigger_not_allowed(self):
        s=translate(PadState(lt=-1,rt=4),0)
        self.assertEqual((s.lt,s.rt),(0,1))

    def test_button_mask_matches_xinput(self):
        s=PadState(frozenset({'A','GUIDE','DPAD_DOWN','START'}))
        self.assertEqual(button_mask(s), 0x1000 | 0x0400 | 0x0002 | 0x0010)

    def test_clamp_saturation(self):
        self.assertEqual(clamp(-100),-1)
        self.assertEqual(clamp(500),1)

if __name__=='__main__':unittest.main()
