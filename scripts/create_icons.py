"""Generate a minimal Windows ICO file without any third-party dependencies.

Usage:
    python scripts/create_icons.py [output_path]

Defaults to packaging/windows/icon.ico relative to the repo root.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


def make_ico(path: Path, size: int = 16, color_bgra: tuple[int, int, int, int] = (46, 134, 255, 255)) -> None:
    """Write a solid-color ICO file containing one BMP image."""
    b, g, r, a = color_bgra

    # XOR mask: size x size pixels, 32-bit BGRA, bottom-up row order
    row = bytes([b, g, r, a]) * size
    xor_pixels = row * size

    # AND mask: all zeros (fully opaque), each row DWORD-aligned
    mask_row_stride = ((size + 31) // 32) * 4
    and_mask = b"\x00" * (mask_row_stride * size)

    # BITMAPINFOHEADER (40 bytes)
    bmp_header = struct.pack(
        "<IiiHHIIiiII",
        40,        # biSize
        size,      # biWidth
        size * 2,  # biHeight — ICO convention: 2x actual height
        1,         # biPlanes
        32,        # biBitCount
        0,         # biCompression (BI_RGB)
        0,         # biSizeImage
        0,         # biXPelsPerMeter
        0,         # biYPelsPerMeter
        0,         # biClrUsed
        0,         # biClrImportant
    )

    image_data = bmp_header + xor_pixels + and_mask

    # ICO file header (6 bytes)
    ico_header = struct.pack("<HHH", 0, 1, 1)  # reserved=0, type=ICO, count=1

    # ICONDIRENTRY (16 bytes)
    img_offset = 6 + 16  # header + one entry
    entry = struct.pack(
        "<BBBBHHII",
        size,              # width  (0 = 256)
        size,              # height (0 = 256)
        0,                 # colorCount (0 = no palette)
        0,                 # reserved
        1,                 # planes
        32,                # bitCount
        len(image_data),   # bytesInRes
        img_offset,        # imageOffset
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ico_header + entry + image_data)
    print(f"Created {path}  ({len(ico_header) + len(entry) + len(image_data)} bytes)")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    default_out = repo_root / "packaging" / "windows" / "icon.ico"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default_out
    make_ico(out)
