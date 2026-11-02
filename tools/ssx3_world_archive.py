"""Append a custom SSX 3 world location to BAM's SDB/SSB archive.

This keeps every retail location and resource stream byte for byte. Callers
must provide a complete leaf texture stream and a complete shared resource
stream for the new location; this module does not invent gameplay resources.
Only write derived archives outside Git (under .cache/).
"""

from __future__ import annotations

from collections import Counter
import math
import struct

from ssx3_world_build import encode_stream
from ssx3_world_probe import read_sdb
from tricky_assets import FormatError


# Retail BAM stores the next global IDs for WorldSSH shapes/lightmaps in the
# otherwise undocumented SDB header. On the USA disc they are 788 and 623;
# scanning all retail kind-9/10 resources independently finds max IDs 787/622.
SHARED_ID_OFFSETS = {9: 42, 10: 44}


def shared_next_id(sdb: bytes, kind: int) -> int:
    """Return the first unused global texture or lightmap ID."""
    offset = SHARED_ID_OFFSETS[kind]
    if len(sdb) < offset + 2:
        raise FormatError("SDB is too short for its shared resource counts")
    value = struct.unpack_from("<h", sdb, offset)[0]
    if value < 0:
        raise FormatError("SDB shared resource count is negative")
    return value


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def pack_bigf(members: list[tuple[str, bytes]]) -> bytes:
    """Build a BIGF container with 2048-byte member alignment."""
    if not members or len(members) > 1024:
        raise ValueError("BIGF needs 1..1024 members")
    names = [name.encode("ascii") for name, _ in members]
    if any(not name or b"\0" in name for name in names) or len(set(names)) != len(names):
        raise ValueError("BIGF member names must be unique ASCII strings")
    header_size = 16 + sum(8 + len(name) + 1 for name in names)
    if header_size > 2048:
        raise ValueError("BIGF member table exceeds one sector")
    out = bytearray(_align(header_size, 2048))
    table = bytearray()
    for (name, data), encoded_name in zip(members, names):
        offset = len(out)
        if offset > 0xffffffff or len(data) > 0xffffffff:
            raise ValueError("BIGF member exceeds the 32-bit extent")
        table.extend(struct.pack(">II", offset, len(data)))
        table.extend(encoded_name + b"\0")
        out.extend(data)
        out.extend(b"\0" * (_align(len(out), 2048) - len(out)))
    if len(out) > 0xffffffff:
        raise ValueError("BIGF archive exceeds the 32-bit length")
    out[:4] = b"BIGF"
    struct.pack_into("<I", out, 4, len(out))
    struct.pack_into(">II", out, 8, len(members), header_size)
    out[16:16 + len(table)] = table
    return bytes(out)


def _records(data: bytes) -> list[tuple[int, int, int, bytes]]:
    result = []
    pos = 0
    while pos < len(data):
        if pos + 8 > len(data):
            raise FormatError("SSB record header is truncated")
        kind = data[pos]
        size = int.from_bytes(data[pos + 1:pos + 4], "little")
        track_id = data[pos + 4]
        rid = int.from_bytes(data[pos + 5:pos + 8], "little")
        end = pos + 8 + size
        if end > len(data):
            raise FormatError("SSB record body is truncated")
        result.append((kind, track_id, rid, data[pos + 8:end]))
        pos = end
    return result


def _hull_descriptor(raw: bytes, stream_id: int, file_offset: int) -> bytes:
    records = _records(raw)
    if len(records) > 65535 or file_offset % 256:
        raise ValueError("SSB stream count/offset is outside its format")
    out = bytearray(68)
    struct.pack_into("<H", out, 0, len(records))
    out[2:5] = stream_id.to_bytes(3, "little")
    out[5:8] = (file_offset // 256).to_bytes(3, "little")
    struct.pack_into("<I", out, 8, len(raw))
    counts = Counter(kind for kind, _, _, _ in records)
    for kind in range(13):
        if counts[kind] > 65535:
            raise ValueError("too many SSB resources of one type")
        struct.pack_into("<H", out, 12 + 2 * kind, counts[kind])
    return bytes(out)


def append_location(sdb: bytes, ssb: bytes, *, name: str,
                    bounds_min: tuple[float, float, float],
                    bounds_max: tuple[float, float, float],
                    leaf_resources: bytes, shared_resources: bytes) -> tuple[bytes, bytes]:
    """Add one leaf section plus a shared stream for a custom course.

    Resources must already have valid SSX 3 payloads and references. The
    returned SDB/SSB pair still needs the other BAM members when packaged.
    """
    locations, chunks, streams = read_sdb(sdb)
    if not name.isascii() or not name or len(name) > 15 or any(c["name"] == name for c in locations):
        raise ValueError("custom world name must be a unique 1..15 byte ASCII name")
    if (len(bounds_min) != 3 or len(bounds_max) != 3 or
            not all(math.isfinite(v) for v in (*bounds_min, *bounds_max)) or
            any(lo >= hi for lo, hi in zip(bounds_min, bounds_max))):
        raise ValueError("custom world needs finite increasing 3D bounds")
    section_id = len(locations)
    leaf_id = len(streams)
    shared_id = leaf_id + 1
    leaf = _records(leaf_resources)
    shared = _records(shared_resources)
    if any(kind not in (9, 10) or track_id != 255 for kind, track_id, _, _ in leaf):
        raise FormatError("leaf stream may contain only shared texture kinds 9 and 10")
    if any(kind in (9, 10) or track_id != section_id
           for kind, track_id, _, _ in shared):
        raise FormatError("location stream has a wrong resource kind or track ID")
    for kind, _, _, payload in shared:
        if kind == 1:
            if len(payload) != 432 or struct.unpack_from("<h", payload, 0x156)[0] != leaf_id:
                raise FormatError("patch does not reference the new leaf stream")
    counts = Counter(kind for kind, _, _, _ in shared)
    if any(count > 32767 for count in counts.values()):
        raise ValueError("location resource count exceeds signed 16-bit format")
    old_loc_end = 80 + len(locations) * 88
    old_chunk_start = _align(old_loc_end, 16)
    old_stream_start = old_chunk_start + len(chunks) * 96
    if old_stream_start + len(streams) * 68 != len(sdb):
        raise FormatError("SDB has an unexpected trailing layout")
    desc = bytearray(88)
    desc[:len(name)] = name.encode("ascii")
    struct.pack_into("<4I", desc, 16, 1, 2, shared_id, len(chunks))
    for kind in range(28):
        struct.pack_into("<h", desc, 32 + 2 * kind, counts[kind])
    node = bytearray(96)
    struct.pack_into("<4f", node, 0, *bounds_min, 1.0)
    struct.pack_into("<4f", node, 16, *bounds_max, 1.0)
    struct.pack_into("<4I", node, 80, 0xffffffff, 0xffffffff, leaf_id, 0)
    out_ssb = bytearray(ssb)
    descriptors = []
    for stream_id, raw in ((leaf_id, leaf_resources), (shared_id, shared_resources)):
        out_ssb.extend(b"\0" * (_align(len(out_ssb), 32 * 1024) - len(out_ssb)))
        descriptors.append(_hull_descriptor(raw, stream_id, len(out_ssb)))
        out_ssb.extend(encode_stream(raw))
    out_sdb = bytearray(sdb[:80])
    struct.pack_into("<3I", out_sdb, 8, len(locations) + 1, len(chunks) + 1,
                     len(streams) + 2)
    for kind in (9, 10):
        highest = max((rid + 1 for k, _, rid, _ in leaf if k == kind), default=0)
        previous = shared_next_id(out_sdb, kind)
        if max(previous, highest) > 32767:
            raise ValueError("shared texture table count exceeds signed 16-bit format")
        struct.pack_into("<h", out_sdb, SHARED_ID_OFFSETS[kind], max(previous, highest))
    out_sdb.extend(sdb[80:old_loc_end])
    out_sdb.extend(desc)
    out_sdb.extend(b"\0" * (_align(len(out_sdb), 16) - len(out_sdb)))
    out_sdb.extend(sdb[old_chunk_start:old_stream_start])
    out_sdb.extend(node)
    out_sdb.extend(sdb[old_stream_start:])
    out_sdb.extend(b"".join(descriptors))
    new_locations, new_chunks, new_streams = read_sdb(out_sdb)
    if (len(new_locations) != len(locations) + 1 or len(new_chunks) != len(chunks) + 1 or
            len(new_streams) != len(streams) + 2 or new_locations[-1]["name"] != name):
        raise FormatError("appended SDB location failed its structural check")
    return bytes(out_sdb), bytes(out_ssb)
