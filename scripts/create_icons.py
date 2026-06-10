"""Generate the app icon assets without any third-party dependencies.

Usage:
    python scripts/create_icons.py [ico_output_path]

By default writes both:
    packaging/windows/icon.ico          (used by PyInstaller + NSIS)
    packaging/linux/tikitakadwh.png     (referenced by AppImageBuilder.yml)
"""

from __future__ import annotations

import struct
import sys
import zlib
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


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def make_png(
    path: Path, size: int = 256, color_rgba: tuple[int, int, int, int] = (255, 134, 46, 255)
) -> None:
    """Write a solid-color PNG (same brand color as the ICO, which stores BGRA)."""
    r, g, b, a = color_rgba
    row = b"\x00" + bytes([r, g, b, a]) * size  # filter byte 0 + RGBA pixels
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(row * size, 9))
        + _png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    print(f"Created {path}  ({len(png)} bytes)")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    if len(sys.argv) > 1:
        make_ico(Path(sys.argv[1]))
    else:
        make_ico(repo_root / "packaging" / "windows" / "icon.ico")
        make_png(repo_root / "packaging" / "linux" / "tikitakadwh.png")
