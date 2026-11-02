"""Build lossless SSX 3 SSB stream envelopes for a future custom world.

The literal RefPack encoder intentionally trades compression for a small,
auditable implementation. Generated game data belongs only in .cache/.
"""

from __future__ import annotations

import struct
import math

from tricky_assets import FormatError, decode_refpack


def encode_refpack_literals(data: bytes) -> bytes:
    """Encode bytes with RefPack's literal commands (no back references)."""
    if len(data) > 0xFFFFFF:
        raise FormatError("one RefPack literal block exceeds the 24-bit length")
    out = bytearray(b"\x10\xfb")
    out.extend(len(data).to_bytes(3, "big"))
    pos = 0
    while len(data) - pos >= 4:
        count = min(112, (len(data) - pos) & ~3)
        out.append(0xE0 + count // 4 - 1)
        out.extend(data[pos:pos + count])
        pos += count
    out.append(0xFC + len(data) - pos)
    out.extend(data[pos:])
    return bytes(out)


def encode_stream(data: bytes, block_bytes: int = 128 * 1024) -> bytes:
    """Wrap uncompressed resources in the SSB CBXS/CEND block format."""
    if not 1 <= block_bytes <= 0xFFFFFF:
        raise ValueError("block_bytes must fit RefPack's 24-bit length")
    out = bytearray()
    chunks = [data[pos:pos + block_bytes] for pos in range(0, len(data), block_bytes)]
    if not chunks:
        chunks = [b""]
    for index, chunk in enumerate(chunks):
        packed = encode_refpack_literals(chunk)
        marker = b"CEND" if index == len(chunks) - 1 else b"CBXS"
        out.extend(marker)
        out.extend(struct.pack("<I", len(packed) + 8))
        out.extend(packed)
    return bytes(out)


def verify_refpack(data: bytes) -> None:
    """Catch changes to the encoder before packaging a custom stream."""
    if decode_refpack(encode_refpack_literals(data)) != data:
        raise FormatError("RefPack literal roundtrip failed")


def pack_resource(kind: int, track_id: int, resource_id: int, payload: bytes) -> bytes:
    """Frame one SSB resource; callers assign IDs and build its references."""
    if not (0 <= kind <= 255 and 0 <= track_id <= 255 and
            0 <= resource_id <= 0xFFFFFF and len(payload) <= 0xFFFFFF):
        raise ValueError("SSB resource header field is out of range")
    return (bytes([kind]) + len(payload).to_bytes(3, "little") +
            bytes([track_id]) + resource_id.to_bytes(3, "little") + payload)


def pack_patch_geometry(source: dict, *, prefix: bytes, object_id: bytes,
                        u10: int, chunk_id: int, texture_rid: int,
                        lightmap_rid: int, tail: bytes,
                        sphere: tuple[float, float, float, float] | None = None) -> bytes:
    """Map one Tricky terrain patch into the 432-byte SSX 3 patch layout.

    The caller must supply the unresolved gameplay/material/section metadata.
    This function preserves the source power-basis coefficients and four
    endpoint positions; it does not invent a material or collision mapping.
    """
    if len(prefix) != 16 or len(object_id) != 4 or len(tail) != 12:
        raise ValueError("SSX 3 patch metadata has the wrong byte length")
    if not all(-0x8000 <= value <= 0x7fff for value in
               (u10, chunk_id, texture_rid, lightmap_rid)):
        raise ValueError("SSX 3 patch short field is out of range")
    lightmap = source["lightmap_vector"]
    uvs = source["uv_vectors"]
    coefficients = source["coefficients"]
    bounds_min = source["bounds_min"]
    bounds_max = source["bounds_max"]
    corners = source["corner_points"]
    if (len(lightmap) != 4 or len(uvs) != 4 or
            any(len(uv) < 2 for uv in uvs) or
            len(coefficients) != 16 or any(len(v) != 4 for v in coefficients) or
            len(bounds_min) != 3 or len(bounds_max) != 3 or
            len(corners) != 4 or any(len(v) < 3 for v in corners)):
        raise ValueError("SSX 3 patch geometry has invalid vector lengths")
    values = (*lightmap, *(v for uv in uvs for v in uv[:2]),
              *(v for vector in coefficients for v in vector),
              *bounds_min, *bounds_max,
              *(v for vector in corners for v in vector[:3]))
    if not all(math.isfinite(v) for v in values):
        raise ValueError("SSX 3 patch geometry has non-finite values")
    if any(lo > hi for lo, hi in zip(bounds_min, bounds_max)):
        raise ValueError("SSX 3 patch geometry has inverted bounds")
    if sphere is None:
        centre = [(lo + hi) / 2 for lo, hi in zip(bounds_min, bounds_max)]
        radius = math.sqrt(sum(((hi - lo) / 2) ** 2
                               for lo, hi in zip(bounds_min, bounds_max)))
        sphere = (*centre, radius)
    if len(sphere) != 4 or not all(math.isfinite(v) for v in sphere):
        raise ValueError("SSX 3 patch bounding sphere is invalid")
    out = bytearray(432)
    out[:16] = prefix
    struct.pack_into("<4f", out, 0x10, *lightmap)
    struct.pack_into("<8f", out, 0x20, *(v for uv in uvs for v in uv[:2]))
    struct.pack_into("<64f", out, 0x40,
                     *(v for vector in coefficients for v in vector))
    struct.pack_into("<4f", out, 0x140, *sphere)
    out[0x150:0x154] = object_id
    struct.pack_into("<2h", out, 0x154, u10, chunk_id)
    struct.pack_into("<6f", out, 0x158, *bounds_min, *bounds_max)
    struct.pack_into("<12f", out, 0x170,
                     *(v for vector in corners for v in vector[:3]))
    struct.pack_into("<2h", out, 0x1a0, texture_rid, lightmap_rid)
    out[0x1a4:] = tail
    return bytes(out)
