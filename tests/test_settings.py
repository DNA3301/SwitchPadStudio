import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from switchpad.settings import DEFAULT, sanitize, load, save, config_path

class SettingsTests(unittest.TestCase):
    def test_defaults_are_deep_copy(self):
        a=sanitize({}); a['raw']['buttons']['A']=999
        self.assertEqual(sanitize({})['raw']['buttons']['A'],1)
    def test_invalid_values_cannot_override(self):
        s=sanitize({'deadzone':-10,'enabled':'true','raw':{'buttons':{'A':'abcdef','X':99_999}}})
        self.assertEqual(s['deadzone'],.12)
        self.assertIs(s['enabled'],True)
        self.assertEqual(s['raw']['buttons']['A'],1)
        self.assertEqual(s['raw']['buttons']['X'],3)
    def test_valid_prefs_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, {'APPDATA':d}):
                s=copy.deepcopy(DEFAULT)
                s['deadzone']=.19; s['nintendo_letters']=True
                s['raw']['buttons']['A']=13
                save(s)
                read=load()
                self.assertEqual(read['deadzone'], .19)
                self.assertTrue(read['nintendo_letters'])
                self.assertEqual(read['raw']['buttons']['A'],13)
                self.assertTrue(config_path().is_file())
    def test_corrupt_json_recovers(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, {'APPDATA':d}):
                p=config_path();p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('{bad json',encoding='utf-8')
                self.assertEqual(load()['deadzone'],.12)

if __name__=='__main__':unittest.main()
