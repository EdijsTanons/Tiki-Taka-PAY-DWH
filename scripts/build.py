"""Cross-platform build helper — wraps PyInstaller + platform-specific packaging.

Usage:
    python scripts/build.py [--platform {windows,macos,linux}]

Defaults to the current platform.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _run(*cmd: str) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(list(cmd), check=True)


def build_pyinstaller() -> None:
    _run(
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "packaging" / "pyinstaller.spec"),
        "--noconfirm",
    )


def _find_makensis() -> str:
    """Return path to makensis.exe, checking PATH then default install locations."""
    import shutil
    found = shutil.which("makensis")
    if found:
        return found
    candidates = [
        Path(r"C:\Program Files (x86)\NSIS\makensis.exe"),
        Path(r"C:\Program Files\NSIS\makensis.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise FileNotFoundError(
        "makensis not found. Install NSIS from https://nsis.sourceforge.io/Download "
        "or add it to your PATH."
    )


def build_windows() -> None:
    build_pyinstaller()
    nsi = ROOT / "packaging" / "windows" / "installer.nsi"
    _run(_find_makensis(), str(nsi))
    print("\nWindows installer built: packaging/windows/TikiTakaPAYDWH-Setup-x64.exe")


def build_macos() -> None:
    build_pyinstaller()
    print(
        "\nPyInstaller bundle built at dist/TikiTakaPAYDWH.\n"
        "Follow packaging/macos/README.md to wrap, sign, and notarise the .app bundle."
    )


def build_linux() -> None:
    build_pyinstaller()
    _run(
        sys.executable, "-m", "appimage_builder",
        "--recipe", str(ROOT / "packaging" / "linux" / "AppImageBuilder.yml"),
        "--skip-tests",
    )
    print("\nLinux AppImage built in packaging/linux/.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux"],
        default=None,
    )
    args = parser.parse_args()

    plat = args.platform or {
        "Windows": "windows",
        "Darwin": "macos",
        "Linux": "linux",
    }.get(platform.system(), "linux")

    print(f"Building for platform: {plat}")

    if plat == "windows":
        build_windows()
    elif plat == "macos":
        build_macos()
    else:
        build_linux()


if __name__ == "__main__":
    main()
