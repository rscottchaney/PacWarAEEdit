"""Side-view aircraft pictures from the game's ART folder.

A_PlaneSide.bmp (Allied) and J_PlaneSide.bmp (Japanese) are uncompressed 24-bit BMPs holding
a grid of 150 x 60 tiles, 4 per row; the tile of an aircraft is its bitmap number (u16 at 26
of the aircraft record). The sheets are read at run time and are not part of the editor. Rows are
read one at a time because a sheet is 13 MB. Every failure is a ValueError, so a caller can turn
any of them into "no picture".
"""

import os
import struct
import zlib

TILE_W, TILE_H = 150, 60
TILES_PER_ROW = 4
SHEETS = {0: "J_PlaneSide.bmp", 1: "A_PlaneSide.bmp"}  # by the model's side id

_cache = {}


def find_sheet(candidates, side_id):
    """Path of the side's sheet in the first candidate ART folder that has it, or None."""
    name = SHEETS.get(side_id)
    for folder in candidates:
        path = os.path.join(folder, name) if name and folder else None
        if path and os.path.isfile(path):
            return path
    return None


def _header(f):
    head = f.read(54)
    if len(head) < 54 or head[:2] != b"BM":
        raise ValueError("not a BMP file")
    data_pos, = struct.unpack_from("<I", head, 10)
    header_size, width, height, _planes, bpp, compression = struct.unpack_from("<IiiHHI", head, 14)
    if header_size < 40 or bpp != 24 or compression != 0:
        raise ValueError("only uncompressed 24-bit BMP files are supported")
    if width <= 0 or height <= 0:
        raise ValueError("unsupported BMP size (top-down or empty)")
    return data_pos, width, height


def sheet_size(path):
    with open(path, "rb") as f:
        _pos, width, height = _header(f)
    return width, height


def read_tile(path, n):
    """The 150 x 60 tile n of the sheet as 60 rows of RGB bytes (450 bytes each, top row first)."""
    with open(path, "rb") as f:
        data_pos, width, height = _header(f)
        x, y = (n % TILES_PER_ROW) * TILE_W, (n // TILES_PER_ROW) * TILE_H
        if n < 0 or x + TILE_W > width or y + TILE_H > height:
            raise ValueError(f"picture {n} is outside the sheet")
        stride = (width * 3 + 3) // 4 * 4  # rows are padded to 4 bytes and stored bottom-up
        rows = []
        for row in range(y, y + TILE_H):
            f.seek(data_pos + (height - 1 - row) * stride + x * 3)
            raw = f.read(TILE_W * 3)
            if len(raw) != TILE_W * 3:
                raise ValueError("the BMP file is truncated")
            rgb = bytearray(raw)
            rgb[0::3], rgb[2::3] = raw[2::3], raw[0::3]  # BGR -> RGB
            rows.append(bytes(rgb))
    return rows


def png(rows):
    """Encode rows of RGB bytes as a PNG file."""
    width = len(rows[0]) // 3

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    raw = b"".join(b"\x00" + row for row in rows)  # filter type 0 on every row
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, len(rows), 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def tile_png(path, n):
    """PNG bytes of tile n, cached per (sheet, n)."""
    key = (path, n)
    if key not in _cache:
        _cache[key] = png(read_tile(path, n))
    return _cache[key]


def plane_png(candidates, side_id, bitmap):
    """PNG of the aircraft picture, searching the candidate ART folders; ValueError if there is none."""
    path = find_sheet(candidates, side_id)
    if path is None:
        raise ValueError("ART folder not found")
    return tile_png(path, bitmap)
