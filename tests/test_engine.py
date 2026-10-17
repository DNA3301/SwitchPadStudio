import copy
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch
from switchpad.engine import classify, read_raw, PadEngine, read_sdl
from switchpad.settings import DEFAULT

class MockJoy:
    def get_name(self): return 'Nintendo Switch Pro Controller'
    def get_vendor(self): return 0x057E
    def get_product(self): return 0x2009
    def get_instance_id(self): return 42
    def get_guid(self): return 'abc123'
    def get_numaxes(self):return 6
    def get_numbuttons(self):return 16
    def get_numhats(self):return 1
    def get_axis(self,i):return {0:.5,1:-.4,2:0,3:.7,4:1.0,5:0}.get(i,0)
    def get_button(self,i):return i in (0,6,11,14)
    def get_hat(self,i):return (1,1)
    def quit(self):pass

class MockController:
    def __init__(self, index):pass
    def as_joystick(self):return MockJoy()
    def quit(self):pass
    def attached(self):return True
    def get_axis(self, axis):return {0:16384, 1:-8192, 2:-16384, 3:8192, 4:32768, 5:0}.get(axis,0)
    def get_button(self, button):return button in (10,14)  # A and DPAD_UP
    def rumble(self,*args):return True

class MockVirtual:
    def __init__(self):
        self.report={};self.updates=0;self.closed=False
    def reset(self):self.report={}
    def press_button(self,button):self.report['buttons']=button
    def left_joystick_float(self,**kw):self.report['left']=kw
    def right_joystick_float(self,**kw):self.report['right']=kw
    def left_trigger_float(self,**kw):self.report['lt']=kw
    def right_trigger_float(self,**kw):self.report['rt']=kw
    def update(self):self.updates+=1
    def register_notification(self,callback_function):self.callback=callback_function
    def unregister_notification(self):self.closed=True

class EngineTests(unittest.TestCase):
    def test_switch_detection_and_virtual_exclusion(self):
        self.assertEqual(classify('Pro Controller', 0,0),(False,True))
        self.assertEqual(classify('Xbox 360 Controller', 0x45E,0x28E),(False,False))
        self.assertEqual(classify('ViGEm Virtual Controller', 0x45E,0x28E),(True,False))
        self.assertEqual(classify('Nintendo Switch 2 Pro', 0x57E,0x2069),(False,True))
    def test_raw_mapping(self):
        s=read_raw(MockJoy(),DEFAULT['raw'])
        self.assertAlmostEqual(s.lx,.5)
        self.assertAlmostEqual(s.ly,.4)
        self.assertIn('DPAD_UP',s.buttons)
        self.assertIn('DPAD_RIGHT',s.buttons)
        self.assertEqual(s.lt,1.0)
    def test_live_emulation_and_stop(self):
        joystick=types.SimpleNamespace(init=lambda:None,quit=lambda:None,get_count=lambda:1,Joystick=lambda idx:MockJoy())
        video=types.SimpleNamespace(init=lambda:None, quit=lambda:None,set_mode=lambda *args,**kw:None)
        pygame=types.ModuleType('pygame')
        pygame.display=video; pygame.joystick=joystick; pygame.event=types.SimpleNamespace(pump=lambda:None)
        pygame.HIDDEN=0;pygame.error=RuntimeError;pygame.get_sdl_version=lambda:(2,30,8)
        for index,name in enumerate(('LEFTX','LEFTY','RIGHTX','RIGHTY','TRIGGERLEFT','TRIGGERRIGHT')):
            setattr(pygame,'CONTROLLER_AXIS_'+name,index)
        for index,name in enumerate(('B','X','Y','LEFTSHOULDER','RIGHTSHOULDER','LEFTSTICK','RIGHTSTICK',
                                     'BACK','GUIDE','START','A','DPAD_DOWN','DPAD_LEFT','DPAD_RIGHT','DPAD_UP')):
            setattr(pygame,'CONTROLLER_BUTTON_'+name,index)
        sdl2=types.ModuleType('pygame._sdl2')
        controller=types.ModuleType('pygame._sdl2.controller')
        controller.init=lambda:None; controller.quit=lambda:None
        controller.is_controller=lambda index:True
        controller.Controller=MockController
        sdl2.controller=controller
        vg=types.ModuleType('vgamepad')
        pads=[]
        def create():
            pad=MockVirtual();pads.append(pad);return pad
        vg.VX360Gamepad=create;vg.XUSB_BUTTON=int
        cfg=copy.deepcopy(DEFAULT)
        with patch.dict(sys.modules,{'pygame':pygame,'pygame._sdl2':sdl2,'pygame._sdl2.controller':controller,'vgamepad':vg}):
            app=PadEngine(cfg)
            app.start()
            try:
                limit=time.time()+2
                while time.time()<limit and not app.get_state().virtual_active:
                    time.sleep(.025)
                snap=app.get_state()
                self.assertTrue(snap.virtual_active, snap.last_error)
                self.assertEqual(snap.selected.name,'Nintendo Switch Pro Controller')
                self.assertEqual(snap.translated.lt,1.0)
                self.assertTrue(pads and pads[0].updates > 0)
                self.assertEqual(pads[0].report['buttons'] & 0x1000,0x1000)
                cfg['enabled']=False; app.update_settings(cfg)
                limit=time.time()+2
                while time.time()<limit and app.get_state().virtual_active:
                    time.sleep(.025)
                self.assertFalse(app.get_state().virtual_active)
                self.assertTrue(pads[0].closed)
            finally:
                app.stop()

if __name__=='__main__':unittest.main()
