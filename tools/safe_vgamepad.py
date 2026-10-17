"""Repackage pinned upstream runtime files without ever executing setup.py.

vgamepad 0.1.0's upstream setup.py invokes an obsolete driver MSI on Windows.
The environment variable used in SwitchPad 3.x does not prevent that action.
This produces a Windows-only wheel from unchanged Python files, x64 client DLL
and MIT license. No driver files or upstream build scripts are executed/copied.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

URL = "https://files.pythonhosted.org/packages/8a/54/0eaddc33f84247963af078f364b37153d09fcd6cdc398f243ec3e8842c56/vgamepad-0.1.0.tar.gz"
SHA256 = "57f6bd01aec0c172947517fb782d150ef9b285f7f4d524c317374fa5c24a89de"
MAX_SIZE = 30 * 1024 * 1024


def runtime_files(data: bytes) -> dict[str, bytes]:
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if not member.isfile() or not parts or parts[0] != "vgamepad-0.1.0" or ".." in parts:
                continue
            name = "/".join(parts[1:])
            allowed = (name.startswith("vgamepad/") and name.endswith(".py")) or name in (
                "vgamepad/win/vigem/client/x64/ViGEmClient.dll", "LICENSE")
            if not allowed:
                continue
            if member.size > MAX_SIZE:
                raise ValueError("Upstream member exceeds size limit")
            stream = archive.extractfile(member)
            if stream is not None:
                files[name] = stream.read(MAX_SIZE + 1)
    required = {"vgamepad/__init__.py", "vgamepad/win/virtual_gamepad.py",
                "vgamepad/win/vigem/client/x64/ViGEmClient.dll", "LICENSE"}
    if not required <= files.keys():
        raise ValueError("Required upstream runtime/license files are missing")
    return files


def build_wheel(data: bytes, destination: Path) -> Path:
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("vgamepad upstream SHA256 mismatch; refusing installation")
    files = runtime_files(data)
    dist = "vgamepad-0.1.0.dist-info"
    files[f"{dist}/licenses/LICENSE"] = files.pop("LICENSE")
    files[f"{dist}/METADATA"] = ("Metadata-Version: 2.1\nName: vgamepad\nVersion: 0.1.0\n"
        "Summary: Upstream vgamepad runtime, repacked without driver installer\n"
        "License: MIT\nLicense-File: licenses/LICENSE\n").encode()
    files[f"{dist}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: SwitchPadStudio-safe-repack\nRoot-Is-Purelib: false\nTag: py3-none-win_amd64\n"
    files[f"{dist}/SWITCHPAD_REPACK.txt"] = ("Unmodified runtime from " + URL + "\nSHA256: " + SHA256 +
        "\nUpstream setup.py and driver installers were not executed or included.\n").encode()
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, content in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, len(content)))
    writer.writerow((f"{dist}/RECORD", "", ""))
    files[f"{dist}/RECORD"] = record.getvalue().encode()
    destination.mkdir(parents=True, exist_ok=True)
    wheel = destination / "vgamepad-0.1.0-py3-none-win_amd64.whl"
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return wheel


def main():
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("This installer requires Windows x64")
    cache = Path(__file__).resolve().parents[1] / "build" / "vendor"
    cache.mkdir(parents=True, exist_ok=True)
    source = cache / "vgamepad-0.1.0.tar.gz"
    if source.is_file():
        if source.stat().st_size > MAX_SIZE:
            raise ValueError("Cached archive exceeds size limit")
        data = source.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise ValueError("Archive exceeds size limit")
    wheel = build_wheel(data, cache)  # verifies the upstream hash before use
    source.write_bytes(data)
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-input", "--no-deps", "--force-reinstall", str(wheel)], check=True)


if __name__ == "__main__":
    main()
