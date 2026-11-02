"""Inspect one SSX 3 world streaming chunk from the local USA ISO.

This is a read-only format probe for the Garibaldi world converter. It reports
the SDB section metadata and SSB resource framing without exporting EA data.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import struct

from tricky_assets import FormatError, decode_refpack, read_iso_file


def bigf_members(archive: bytes) -> dict[str, bytes]:
    if len(archive) < 16 or archive[:4] != b"BIGF":
        raise FormatError("SSX 3 world archive is not BIGF")
    count, header_size = struct.unpack_from(">II", archive, 8)
    if count > 1024 or not 16 <= header_size <= len(archive):
        raise FormatError("invalid SSX 3 BIGF header")
    pos = 16
    members = {}
    for _ in range(count):
        if pos + 8 > header_size:
            raise FormatError("truncated BIGF table")
        offset, size = struct.unpack_from(">II", archive, pos)
        end = archive.find(b"\x00", pos + 8, header_size + 16)
        if end < 0 or offset < header_size or offset + size > len(archive):
            raise FormatError("invalid BIGF member extent or name")
        name = archive[pos + 8:end].decode("ascii", "replace").lower()
        members[name] = archive[offset:offset + size]
        pos = end + 1
    return members


def read_sdb(data: bytes) -> tuple[list[dict], list[dict], list[dict]]:
    if len(data) < 80 or data[:4] != b"\x00\x38\x00\x01":
        raise FormatError("unsupported SSX 3 SDB version")
    location_count, chunk_count, stream_count = struct.unpack_from("<3I", data, 8)
    if location_count > 1024 or chunk_count > 100_000 or stream_count > 100_000:
        raise FormatError("invalid SSX 3 SDB counts")
    location_offset = 80
    chunk_offset = (location_offset + location_count * 88 + 15) & ~15
    stream_offset = chunk_offset + chunk_count * 96
    if stream_offset + stream_count * 68 > len(data):
        raise FormatError("SSX 3 SDB tables extend beyond the file")
    locations = []
    for index in range(location_count):
        pos = location_offset + index * 88
        name = data[pos:pos + 16].split(b"\x00", 1)[0].decode("ascii", "replace")
        num_chunks, num_streams, last_stream, first_chunk = struct.unpack_from("<4I", data, pos + 16)
        if (num_streams > stream_count or last_stream >= stream_count or
                last_stream + 1 < num_streams or first_chunk + num_chunks > chunk_count):
            raise FormatError(f"SDB location {name} has invalid chunk ranges")
        locations.append({
            "index": index,
            "name": name,
            "chunk_count": num_chunks,
            "stream_count": num_streams,
            "first_stream": last_stream + 1 - num_streams,
            "last_stream": last_stream,
            "first_chunk": first_chunk,
        })
    chunks = []
    for index in range(chunk_count):
        pos = chunk_offset + index * 96
        low = struct.unpack_from("<4f", data, pos)
        high = struct.unpack_from("<4f", data, pos + 16)
        child1, child2, streaming_id, extra = struct.unpack_from("<4I", data, pos + 80)
        chunks.append({
            "index": index,
            "bounds_min": list(low),
            "bounds_max": list(high),
            "child1": child1,
            "child2": child2,
            "streaming_chunk_id": streaming_id,
            "extra": extra,
        })
    streams = []
    for index in range(stream_count):
        pos = stream_offset + index * 68
        num_resources = struct.unpack_from("<H", data, pos)[0]
        subchunk_id = int.from_bytes(data[pos + 2:pos + 5], "little")
        file_offset = int.from_bytes(data[pos + 5:pos + 8], "little") * 256
        unpacked_size = struct.unpack_from("<I", data, pos + 8)[0]
        resource_counts = struct.unpack_from("<13H", data, pos + 12)
        streams.append({
            "index": index,
            "num_resources": num_resources,
            "subchunk_id": subchunk_id,
            "file_offset": file_offset,
            "unpacked_size": unpacked_size,
            "resource_counts_0_to_12": list(resource_counts),
        })
    return locations, chunks, streams


def decode_stream(ssb: bytes, stream: dict) -> bytes:
    pos = stream["file_offset"]
    unpacked = bytearray()
    for _ in range(100_000):
        if pos + 8 > len(ssb):
            raise FormatError("SSB compressed block header is truncated")
        magic = ssb[pos:pos + 4]
        size = struct.unpack_from("<I", ssb, pos + 4)[0]
        if magic not in (b"CBXS", b"CEND") or size < 8 or pos + size > len(ssb):
            raise FormatError(f"invalid SSB compressed block at {pos:#x}")
        unpacked.extend(decode_refpack(ssb[pos + 8:pos + size]))
        # Retail BAM's reported unpacked size is often an underestimate.
        # Its ARA1 terrain stream reports 4,734,956, but expands to
        # 5,155,109 bytes. Validate a generous hard bound and the resources.
        if len(unpacked) > 128 * 1024 * 1024:
            raise FormatError("SSB stream exceeds the safe expansion limit")
        pos += size
        if magic == b"CEND":
            break
    else:
        raise FormatError("SSB compressed stream has no final block")
    return unpacked


def resource_summary(data: bytes, expected: int) -> dict:
    pos = 0
    counts = Counter()
    sizes = {}
    track_ids = set()
    patch_corner_error = 0.0
    patch_texture_ids = set()
    patch_chunk_ids = set()
    for _ in range(expected):
        if pos + 8 > len(data):
            raise FormatError("SSB resource header extends beyond stream")
        kind = data[pos]
        size = int.from_bytes(data[pos + 1:pos + 4], "little")
        track_id = data[pos + 4]
        resource_id = int.from_bytes(data[pos + 5:pos + 8], "little")
        if pos + 8 + size > len(data):
            raise FormatError(f"SSB resource {kind}:{resource_id} is truncated")
        counts[kind] += 1
        sizes.setdefault(kind, set()).add(size)
        track_ids.add(track_id)
        if kind == 1:
            if size != 432:
                raise FormatError(f"SSX 3 patch has unexpected payload size {size}")
            payload = pos + 8
            coefficients = struct.unpack_from("<64f", data, payload + 0x40)
            # The six vec3 fields after the chunk ID are: axis-aligned
            # min/max, followed by the four polynomial endpoint positions.
            # SSX-Library calls the first two Point1/Point2 and the last two
            # BBoxMin/BBoxMax, but the retail data proves their actual roles.
            bounds_min = struct.unpack_from("<3f", data, payload + 0x158)
            bounds_max = struct.unpack_from("<3f", data, payload + 0x164)
            if any(lo > hi for lo, hi in zip(bounds_min, bounds_max)):
                raise FormatError("SSX 3 patch has inverted bounds")
            corners = [struct.unpack_from("<3f", data, payload + 0x170 + 12 * i)
                       for i in range(4)]
            if not all(math.isfinite(value) for value in coefficients):
                raise FormatError("SSX 3 patch has non-finite coefficients")
            vectors = [coefficients[4 * i:4 * i + 3] for i in range(16)]
            for corner, terms in enumerate(((15,), (3, 7, 11, 15),
                                            (12, 13, 14, 15), tuple(range(16)))):
                for axis in range(3):
                    patch_corner_error = max(
                        patch_corner_error,
                        abs(sum(vectors[i][axis] for i in terms) - corners[corner][axis]),
                    )
            patch_chunk_ids.add(struct.unpack_from("<h", data, payload + 0x156)[0])
            patch_texture_ids.add(struct.unpack_from("<h", data, payload + 0x1A0)[0])
        pos += 8 + size
    if pos != len(data):
        raise FormatError(f"SSB stream has {len(data) - pos} trailing bytes")
    if patch_corner_error > 0.25:
        raise FormatError(f"SSX 3 patch endpoint mismatch: {patch_corner_error}")
    return {
        "resource_counts": dict(sorted(counts.items())),
        "resource_sizes": {
            kind: {"min": min(values), "max": max(values), "variants": len(values)}
            for kind, values in sorted(sizes.items())
        },
        "track_ids": sorted(track_ids),
        "patch_corner_max_abs_error": patch_corner_error,
        "patch_streaming_chunk_ids": sorted(patch_chunk_ids),
        "patch_texture_id_count": len(patch_texture_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path,
                        default=Path(os.environ.get("SSX3_ISO", "SSX 3 (USA).iso")))
    parser.add_argument("--location", default="ARA1")
    parser.add_argument("--stream", type=int, default=-1,
                        help="stream index within the location (default: final stream)")
    args = parser.parse_args()
    try:
        system = read_iso_file(args.iso, "SYSTEM.CNF")
        if b"SLUS_207.72" not in system:
            raise FormatError(f"{args.iso}: expected SSX 3 USA (SLUS_207.72)")
        archive = read_iso_file(args.iso, "DATA/WORLDS/BAM.BIG")
        members = bigf_members(archive)
        sdb = members["data/worlds/bam.sdb"]
        ssb = members["data/worlds/bam.ssb"]
        locations, chunks, streams = read_sdb(sdb)
        location = next((entry for entry in locations
                         if entry["name"].casefold() == args.location.casefold()), None)
        if location is None:
            raise FormatError(f"unknown BAM location {args.location!r}")
        index = args.stream if args.stream >= 0 else location["stream_count"] + args.stream
        if not 0 <= index < location["stream_count"]:
            raise FormatError(f"stream index {args.stream} outside {args.location}")
        stream = streams[location["first_stream"] + index]
        unpacked = decode_stream(ssb, stream)
        summary = resource_summary(unpacked, stream["num_resources"])
        for kind, count in enumerate(stream["resource_counts_0_to_12"]):
            if summary["resource_counts"].get(kind, 0) != count:
                raise FormatError(f"SDB/SSB resource count mismatch for kind {kind}")
        location_chunks = chunks[location["first_chunk"]:
                                 location["first_chunk"] + location["chunk_count"]]
        chunk_ids = {chunk["index"] for chunk in location_chunks}
        for chunk in location_chunks:
            for child in (chunk["child1"], chunk["child2"]):
                if child != 0xffffffff and child not in chunk_ids:
                    raise FormatError(f"location {location['name']} points outside its chunk tree")
    except (OSError, FormatError, KeyError) as error:
        parser.exit(2, f"SSX 3 world probe: {error}\n")
    print(json.dumps({
        "world_locations": len(locations),
        "world_streams": len(streams),
        "location": location,
        "location_chunks": location_chunks,
        "stream": stream,
        "actual_unpacked_size": len(unpacked),
        **summary,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
