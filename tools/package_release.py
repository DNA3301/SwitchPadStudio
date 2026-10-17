"""Package a committed source tree and the locally verified Windows EXE."""
import hashlib
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "4.0.0-beta.1"


def main():
    exe = ROOT / "SwitchPadStudio.exe"
    if not exe.is_file():
        raise SystemExit("Build and verify SwitchPadStudio.exe first")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        raise SystemExit("Commit the reviewed source tree before packaging")
    out = ROOT / "release"
    out.mkdir(exist_ok=True)
    source = out / f"SwitchPadStudio-{VERSION}-source.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--output={source}", "HEAD"], cwd=ROOT, check=True)
    package = out / f"SwitchPadStudio-{VERSION}-Windows-x64.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in (exe, ROOT / "README.md", ROOT / "TEST_REPORT.md", ROOT / "RELEASE_NOTES.md"):
            archive.write(file, file.name)
        for file in sorted((ROOT / "third_party").rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(ROOT).as_posix())
        archive.write(source, "SOURCE.zip")
    checksums = []
    for file in (exe, source, package):
        checksums.append(f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}")
    (out / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8", newline="\n")
    print(package.name, package.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
