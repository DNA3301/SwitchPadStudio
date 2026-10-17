"""Only SDL is required by this controller bridge; no audio/image/font codecs."""
from pathlib import Path
from PyInstaller.utils.hooks import get_package_paths

_, package = get_package_paths("pygame")
binaries = [(str(Path(package) / "SDL2.dll"), "pygame")]
datas = []
