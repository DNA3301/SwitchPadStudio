import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.safe_vgamepad import runtime_files, build_wheel


def source_archive():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        files = {"vgamepad/__init__.py": b"# original runtime",
                 "vgamepad/win/virtual_gamepad.py": b"# original engine",
                 "vgamepad/win/vigem/client/x64/ViGEmClient.dll": b"test DLL",
                 "LICENSE": b"MIT test notice",
                 "setup.py": b"raise RuntimeError('MUST NEVER EXECUTE')",
                 "vgamepad/win/vigem/install/x64/ViGEmBusSetup_x64.msi": b"driver",
                 "vgamepad/../../escape.py": b"bad"}
        for name, content in files.items():
            info = tarfile.TarInfo("vgamepad-0.1.0/" + name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class SafeInstallTests(unittest.TestCase):
    def test_copies_unchanged_runtime_and_license_only(self):
        files = runtime_files(source_archive())
        self.assertEqual(len(files), 4)
        self.assertEqual(files["vgamepad/__init__.py"], b"# original runtime")
        self.assertFalse(any("setup" in name.lower() or ".." in name for name in files))

    def test_rejects_untrusted_archive_before_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "SHA256"):
                build_wheel(source_archive(), Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_wheel_contains_records_without_driver_installers(self):
        data = source_archive()
        with tempfile.TemporaryDirectory() as directory, patch("tools.safe_vgamepad.SHA256", hashlib.sha256(data).hexdigest()):
            wheel = build_wheel(data, Path(directory))
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                self.assertFalse(any(name.endswith((".msi", "setup.py")) for name in names))
                self.assertIn("vgamepad-0.1.0.dist-info/RECORD", names)
                self.assertIn("vgamepad-0.1.0.dist-info/licenses/LICENSE", names)


if __name__ == "__main__":
    unittest.main()
