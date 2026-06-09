"""Set the project version in every place it is recorded.

Usage:
    python scripts/bump_version.py 0.3.0

Updates:
    pyproject.toml                       [project] version
    src/tikitaka_dwh/__init__.py         __version__
    packaging/windows/installer.nsi      APP_VERSION / VER_MAJOR / VER_MINOR
    packaging/macos/Info.plist           CFBundleVersion / CFBundleShortVersionString
    packaging/linux/AppImageBuilder.yml  AppDir.app_info.version / AppImage.version

The script fails loudly if any file does not contain the expected number of
version strings, so a layout change can never silently leave a file stale.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _sub(path: Path, pattern: str, repl: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(pattern, repl, text)
    if n != expected:
        sys.exit(
            f"ERROR: expected {expected} replacement(s) in {path.name}, made {n} — "
            "file layout changed? Fix the pattern in scripts/bump_version.py."
        )
    path.write_text(new_text, encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}  ({n})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set the project version everywhere.")
    parser.add_argument("version", help="New semantic version, e.g. 0.3.0")
    args = parser.parse_args()

    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", args.version)
    if not m:
        sys.exit("ERROR: version must be MAJOR.MINOR.PATCH, e.g. 0.3.0")
    major, minor, _ = m.groups()
    v = args.version

    print(f"Setting version {v} in:")
    _sub(
        ROOT / "pyproject.toml",
        r'(?m)^version = "[^"]+"$',
        f'version = "{v}"',
        expected=1,
    )
    _sub(
        ROOT / "src" / "tikitaka_dwh" / "__init__.py",
        r'__version__ = "[^"]+"',
        f'__version__ = "{v}"',
        expected=1,
    )
    nsi = ROOT / "packaging" / "windows" / "installer.nsi"
    _sub(nsi, r'!define APP_VERSION\s+"[^"]+"', f'!define APP_VERSION     "{v}"', expected=1)
    _sub(nsi, r'!define VER_MAJOR\s+"[^"]+"', f'!define VER_MAJOR       "{major}"', expected=1)
    _sub(nsi, r'!define VER_MINOR\s+"[^"]+"', f'!define VER_MINOR       "{minor}"', expected=1)
    plist = ROOT / "packaging" / "macos" / "Info.plist"
    _sub(
        plist,
        r"(<key>CFBundleVersion</key>\s*<string>)[^<]+(</string>)",
        rf"\g<1>{v}\g<2>",
        expected=1,
    )
    _sub(
        plist,
        r"(<key>CFBundleShortVersionString</key>\s*<string>)[^<]+(</string>)",
        rf"\g<1>{v}\g<2>",
        expected=1,
    )
    _sub(
        ROOT / "packaging" / "linux" / "AppImageBuilder.yml",
        r"(?m)^(\s*version: )\d+\.\d+\.\d+$",
        rf"\g<1>{v}",
        expected=2,
    )
    print("Done.  Remember to add a changelog entry in README.md.")


if __name__ == "__main__":
    main()
