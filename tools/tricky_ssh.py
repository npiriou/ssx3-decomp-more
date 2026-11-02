"""Repackage Tricky PS2 SSH images as SSX 3 world texture resources.

Tricky SHPS can store linear texels and palettes; the target declares its
TexMan pixel layout and uses the PS2 CLUT permutation. Tricky SHPS
entries use 16-byte subheaders; SSX 3 world SSH entries use 128-byte headers
for both the image and palette. No texture image is stored in this repository.
"""

from __future__ import annotations

import struct

from tricky_assets import FormatError


def _psmt8_palette(linear: bytes) -> bytes:
    """PSMT8 CLUT addressing exchanges index bits 3 and 4."""
    result = bytearray(1024)
    for index in range(256):
        slot = (index & ~0x18) | ((index & 8) << 1) | ((index & 16) >> 1)
        result[slot * 4:slot * 4 + 4] = linear[index * 4:index * 4 + 4]
    return bytes(result)


def parse_shps(data: bytes) -> list[tuple[int, bytes]]:
    if len(data) < 16 or data[:4] != b"SHPS":
        raise FormatError("Tricky SSH is not an SHPS container")
    declared, count = struct.unpack_from("<2I", data, 4)
    if declared != len(data) or count > 10_000 or 16 + 8 * count > len(data):
        raise FormatError("Tricky SSH header or image table is invalid")
    offsets = []
    for index in range(count):
        name = data[16 + 8 * index:20 + 8 * index]
        if not name.isdigit():
            raise FormatError("Tricky SSH image name is not a numeric ID")
        off = struct.unpack_from("<I", data, 20 + 8 * index)[0]
        offsets.append((int(name), off))
    if len({rid for rid, _ in offsets}) != count:
        raise FormatError("Tricky SSH has duplicate image IDs")
    result = []
    for index, (rid, off) in enumerate(offsets):
        end = offsets[index + 1][1] if index + 1 < count else len(data)
        if off < 16 + 8 * count or end <= off or end > len(data):
            raise FormatError("Tricky SSH image extent is invalid")
        result.append((rid, data[off:end]))
    return result


def to_world_ssh(source: bytes, *, lightmap: bool) -> bytes:
    """Convert one image entry; caller assigns its global SSX 3 RID."""
    if len(source) < 16:
        raise FormatError("Tricky SSH image is truncated")
    fmt = source[0]
    size = int.from_bytes(source[1:4], "little")
    width, height = struct.unpack_from("<2H", source, 4)
    if not 1 <= width <= 2048 or not 1 <= height <= 2048:
        raise FormatError("Tricky SSH image has invalid dimensions")
    if lightmap:
        if fmt != 5 or size != 16 + width * height * 4:
            raise FormatError("expected a 32-bit Tricky lightmap")
        if len(source) < size:
            raise FormatError("Tricky lightmap texels are truncated")
        header = bytearray(128)
        header[0] = 5
        struct.pack_into("<2H", header, 4, width, height)
        header[13] = 0x10  # Retail WorldSSH's 32-bit texture mode.
        struct.pack_into("<I", header, 16, 128)
        return bytes(header) + source[16:size]
    if fmt != 2 or size != 16 + width * height:
        raise FormatError("expected an 8-bit indexed Tricky texture")
    if size + 16 + 1024 > len(source) or source[size] != 0x21:
        raise FormatError("Tricky texture palette is missing or truncated")
    header = bytearray(128)
    header[0] = 2
    header[1:4] = (128 + width * height).to_bytes(3, "little")
    struct.pack_into("<2H", header, 4, width, height)
    swizzled_pixels = bool(struct.unpack_from("<I", source, 12)[0] & 0x2000)
    # 0x1000 selects the relative data offset at +0x10. 0x2000 selects
    # TexMan's pre-swizzled format 10; clear it for native linear format 9.
    header[13] = 0x30 if swizzled_pixels else 0x10
    struct.pack_into("<I", header, 16, 128)
    palette = bytearray(128)
    palette[0] = 0x21
    struct.pack_into("<3H", palette, 4, 256, 1, 256)
    palette[13] = 0x30
    struct.pack_into("<I", palette, 16, 128)
    pixels = source[16:size]
    colours = source[size + 16:size + 16 + 1024]
    if not struct.unpack_from("<I", source, size + 12)[0] & 0x2000:
        colours = _psmt8_palette(colours)
    return bytes(header) + pixels + bytes(palette) + colours


def inspect_world_ssh(data: bytes, *, lightmap: bool) -> dict:
    """Check the target header, body, and palette envelope."""
    if len(data) < 128:
        raise FormatError("WorldSSH is shorter than its header")
    fmt = data[0]
    width, height = struct.unpack_from("<2H", data, 4)
    size = int.from_bytes(data[1:4], "little")
    if lightmap:
        if fmt != 5 or size != 0 or len(data) != 128 + width * height * 4:
            raise FormatError("WorldSSH lightmap layout is invalid")
    elif (fmt != 2 or size != 128 + width * height or
          len(data) != size + 128 + 1024 or data[size] != 0x21):
        raise FormatError("WorldSSH indexed texture layout is invalid")
    return {"format": fmt, "width": width, "height": height, "bytes": len(data)}
